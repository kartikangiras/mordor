"""NASA FIRMS active-fire fetch, normalisation, storage and lookup (DESIGN.md §4.1).

Two fetch paths through one normaliser:
  * area API   - needs FIRMS_MAP_KEY, domain bbox, DAY_RANGE=2
  * regional   - keyless South-Asia 48 h CSV feeds (verified 2026-09-26), filtered to the domain
The raw CSV is cached in storage at raw/firms/{utc_date}/{source}.csv and indexed in DynamoDB.
"""
from __future__ import annotations

import csv
import io
import logging
import statistics
from datetime import datetime, timedelta

import requests

from common import ddb, domain
from common.storage import storage
from common.timeutil import iso_z, parse_firms_time, ttl_epoch, utc_date_str, utc_now

log = logging.getLogger(__name__)

AREA_BASE = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
DAY_RANGE = 2
FIRE_TTL_DAYS = 30
SOURCES: tuple[str, ...] = ("VIIRS_NOAA20_NRT", "VIIRS_SNPP_NRT", "VIIRS_NOAA21_NRT")

_FEED = "https://firms.modaps.eosdis.nasa.gov/data/active_fire"
REGIONAL_FEEDS: dict[str, str] = {
    "VIIRS_NOAA20_NRT": f"{_FEED}/noaa-20-viirs-c2/csv/J1_VIIRS_C2_South_Asia_48h.csv",
    "VIIRS_SNPP_NRT": f"{_FEED}/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_South_Asia_48h.csv",
    "VIIRS_NOAA21_NRT": f"{_FEED}/noaa-21-viirs-c2/csv/J2_VIIRS_C2_South_Asia_48h.csv",
}

TIMEOUT = 45


def area_url(map_key: str, source: str, day_range: int = DAY_RANGE, date: str | None = None) -> str:
    w, s, e, n = domain.DOMAIN_WSEN
    url = f"{AREA_BASE}/{map_key}/{source}/{w},{s},{e},{n}/{day_range}"
    return f"{url}/{date}" if date else url


def fetch_csv(source: str, map_key: str | None = None, session: requests.Session | None = None) -> tuple[str, str]:
    """Return (csv_text, provenance). provenance is 'area' or 'regional'."""
    sess = session or requests.Session()
    if map_key:
        resp = sess.get(area_url(map_key, source), timeout=TIMEOUT)
        resp.raise_for_status()
        text = resp.text
        if text.lower().startswith("invalid") or "latitude" not in text[:200]:
            raise RuntimeError(f"FIRMS area API rejected request for {source}: {text[:120]!r}")
        return text, "area"
    resp = sess.get(REGIONAL_FEEDS[source], timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.text, "regional"


def normalise_confidence(raw) -> str:
    """VIIRS: 'low|nominal|high' (feeds) or 'l|n|h' (area API). MODIS: integer 0-100."""
    v = str(raw).strip().lower()
    if v in ("l", "low"):
        return "low"
    if v in ("n", "nominal"):
        return "nominal"
    if v in ("h", "high"):
        return "high"
    try:
        n = float(v)
    except ValueError:
        return "nominal"
    return "low" if n < 30 else ("nominal" if n < 80 else "high")


def _float(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f else None


def parse_fires(csv_text: str, source: str) -> list[dict]:
    """CSV -> list of normalised detections inside the domain with confidence != low."""
    out: list[dict] = []
    for row in csv.DictReader(io.StringIO(csv_text)):
        lat, lon = _float(row.get("latitude")), _float(row.get("longitude"))
        if lat is None or lon is None or not bool(domain.in_domain(lat, lon)):
            continue
        conf = normalise_confidence(row.get("confidence", ""))
        if conf == "low":
            continue
        try:
            acq = parse_firms_time(row["acq_date"], row["acq_time"])
        except (KeyError, ValueError):
            continue
        frp = _float(row.get("frp"))
        out.append({
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "frp": frp if frp is not None and frp > 0 else None,
            "confidence": conf,
            "satellite": (row.get("satellite") or "").strip(),
            "daynight": (row.get("daynight") or "").strip(),
            "brightness": _float(row.get("bright_ti4") or row.get("brightness")),
            "acqUtc": iso_z(acq),
            "source": source,
        })
    return out


def dedupe(fires: list[dict]) -> list[dict]:
    seen: dict[tuple, dict] = {}
    for f in fires:
        seen.setdefault((f["acqUtc"], f["lat"], f["lon"]), f)
    return list(seen.values())


def dedupe_cross_satellite(fires: list[dict], km: float = 1.0, minutes: float = 90.0) -> list[dict]:
    """Merge detections of the same fire by different satellites (or the same satellite's
    overlapping swaths): within `km` and `minutes`, keep the detection with the largest FRP.
    Keeps the emission basis consistent with the single-satellite (SNPP) hindcast that fits k."""
    import math

    fires = sorted(fires, key=lambda f: f["acqUtc"])
    cell = km / 111.32
    buckets: dict[tuple, list[dict]] = {}
    kept: list[dict] = []
    for f in fires:
        key = (int(f["lat"] // cell), int(f["lon"] // cell))
        t = datetime.fromisoformat(f["acqUtc"].replace("Z", "+00:00"))
        merged = False
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                for g in buckets.get((key[0] + dy, key[1] + dx), []):
                    tg = datetime.fromisoformat(g["acqUtc"].replace("Z", "+00:00"))
                    if abs((t - tg).total_seconds()) > minutes * 60:
                        continue
                    dlat = (f["lat"] - g["lat"]) * 111.32
                    dlon = (f["lon"] - g["lon"]) * 111.32 * math.cos(math.radians(f["lat"]))
                    if math.hypot(dlat, dlon) <= km:
                        if (f["frp"] or 0) > (g["frp"] or 0):
                            g.update({k: f[k] for k in ("lat", "lon", "frp", "satellite", "source", "confidence", "brightness")})
                        g["nSat"] = g.get("nSat", 1) + 1
                        merged = True
                        break
                if merged:
                    break
            if merged:
                break
        if not merged:
            kept.append(f)
            buckets.setdefault(key, []).append(f)
    return kept


def fill_missing_frp(fires: list[dict]) -> int:
    """FRP missing or <= 0 -> median of the rest (§5.3). Returns how many were filled."""
    known = [f["frp"] for f in fires if f["frp"] is not None]
    med = statistics.median(known) if known else 1.0
    n = 0
    for f in fires:
        if f["frp"] is None:
            f["frp"] = med
            f["frpFilled"] = True
            n += 1
    return n


def to_ddb_items(fires: list[dict], now: datetime | None = None) -> list[dict]:
    ttl = ttl_epoch(FIRE_TTL_DAYS, now)
    items = []
    for f in fires:
        items.append({
            "PK": ddb.fire_pk(f["acqUtc"][:10]),
            "SK": ddb.fire_sk(f["acqUtc"], f["lat"], f["lon"]),
            **{k: v for k, v in f.items() if k not in ("acqUtc",)},
            "acqUtc": f["acqUtc"],
            "ttl": ttl,
        })
    return items


def to_geojson(fires: list[dict]) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [f["lon"], f["lat"]]},
                "properties": {k: f[k] for k in ("frp", "confidence", "satellite", "daynight", "acqUtc", "source") if k in f},
            }
            for f in fires
        ],
    }


def raw_key(source: str, now: datetime) -> str:
    return f"raw/firms/{utc_date_str(now)}/{source}.csv"


def run(now: datetime | None = None, map_key: str | None = None) -> dict:
    """Fetch every source, cache raw CSV, index detections. Returns a summary for the log."""
    now = now or utc_now()
    sess = requests.Session()
    all_fires: list[dict] = []
    summary: dict = {"fetchedAt": iso_z(now), "sources": {}}
    for source in SOURCES:
        try:
            text, prov = fetch_csv(source, map_key, sess)
        except Exception as exc:  # noqa: BLE001 - one bad source must not sink the run
            log.warning("FIRMS %s fetch failed: %s", source, exc)
            summary["sources"][source] = {"error": str(exc)[:200]}
            continue
        storage().put_text(raw_key(source, now), text, "text/csv")
        fires = parse_fires(text, source)
        summary["sources"][source] = {"provenance": prov, "rows": text.count("\n"), "inDomain": len(fires)}
        all_fires.extend(fires)
    fires = dedupe(all_fires)
    filled = fill_missing_frp(fires)
    written = ddb.put_items(to_ddb_items(fires, now))
    summary.update({"detections": len(fires), "frpFilled": filled, "ddbWritten": written})
    log.info("firms ingest: %s", summary)
    return summary


def load_recent(hours: int = 24, now: datetime | None = None) -> list[dict]:
    """Detections in the last `hours`. DynamoDB when enabled, else the cached raw CSVs."""
    now = now or utc_now()
    cutoff = iso_z(now - timedelta(hours=hours))
    days = {utc_date_str(now), utc_date_str(now - timedelta(hours=hours))}
    fires: list[dict] = []
    if ddb.enabled():
        for day in sorted(days):
            for item in ddb.query(ddb.fire_pk(day)):
                fires.append({k: v for k, v in item.items() if k not in ("PK", "SK", "ttl")})
    else:
        for day in sorted(days):
            for key in storage().list(f"raw/firms/{day}/"):
                if not key.endswith(".csv"):
                    continue
                source = key.rsplit("/", 1)[-1][:-4]
                text = storage().get_text(key)
                if text:
                    fires.extend(parse_fires(text, source))
    fires = [f for f in dedupe(fires) if f["acqUtc"] >= cutoff and f["acqUtc"] <= iso_z(now)]
    fill_missing_frp(fires)
    fires = dedupe_cross_satellite(fires)
    fires.sort(key=lambda f: f["acqUtc"])
    return fires
