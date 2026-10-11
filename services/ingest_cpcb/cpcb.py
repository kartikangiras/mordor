"""Live station observations (DESIGN.md §4.3): OpenAQ v3 first, data.gov.in when it answers.

Two sources, merged into one snapshot:

  * **OpenAQ v3** (`openaq_live.py`) is the live layer. It is the only route to hourly station
    data that works today; see that module for why, and for the `tier` field that separates
    reference monitors from low-cost sensors.
  * **data.gov.in** is still attempted whenever `data_gov_api_key` is set, because it is the
    reference-grade CPCB feed and we want it the moment NIC brings the host back. Its host has
    refused connections since 2026-10-06, so a failure here is logged and skipped, never fatal.

Rows from data.gov.in are one per station per pollutant; we pivot to PM2.5 (and PM10) per
station, keep only stations inside the domain with a parseable value, and store:
  raw/cpcb/{date}/{HH}.json   the data.gov.in rows as received, when it answers
  live/cpcb/latest.json       the merged snapshot the API serves
  DynamoDB STATION#{id}/OBS#{hour}  one observation per station-hour (30 d TTL)
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
from datetime import datetime

import requests

from common import ddb, domain
from common.storage import storage
from common.timeutil import floor_hour, iso_z, parse_cpcb_last_update, ttl_epoch, utc_now

log = logging.getLogger(__name__)

BASE = "https://api.data.gov.in/resource/"
# The catalog https://www.data.gov.in/catalog/real-time-air-quality-index listed exactly this
# API id on 2026-10-07 (the older 3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69 is gone), but it could
# not be confirmed against a live response because api.data.gov.in refuses connections. It is
# an env var so it can be corrected with update-function-configuration, no rebuild.
RESOURCE_ID = os.environ.get("CPCB_RESOURCE_ID", "a3e7afc6-b799-4ede-b143-8e074b27e062")
PAGE = 1000
MAX_PAGES = 10
TIMEOUT = 45
OBS_TTL_DAYS = 30
LATEST_KEY = "live/cpcb/latest.json"

#: `live/cpcb/latest.json` is served publicly by GET /api/stations/latest, and a requests
#: exception stringifies the full URL, so a data.gov.in failure would otherwise publish
#: `api-key=<the key>` to the internet. Redact before anything reaches the snapshot.
_SECRET_QS = re.compile(r"((?:api[-_]?key|key|token)=)[^&\s\"']+", re.I)


def redact(text: str) -> str:
    """Mask credentials that appear in a URL or error string."""
    return _SECRET_QS.sub(r"\1***", str(text))


_PM25 = {"pm2.5", "pm2_5", "pm25"}
_PM10 = {"pm10"}


def fetch_rows(api_key: str, session: requests.Session | None = None, resource_id: str = RESOURCE_ID) -> list[dict]:
    sess = session or requests.Session()
    rows: list[dict] = []
    for page in range(MAX_PAGES):
        params = {"api-key": api_key, "format": "json", "limit": PAGE, "offset": page * PAGE}
        resp = sess.get(f"{BASE}{resource_id}", params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        if "records" not in data:
            raise RuntimeError(f"data.gov.in unexpected response: {str(data)[:200]}")
        batch = data["records"]
        rows.extend(batch)
        if len(batch) < PAGE:
            break
    return rows


def _num(v) -> float | None:
    if v is None:
        return None
    s = str(v).strip()
    if not s or s.upper() in ("NA", "N/A", "NAN", "NULL", "-"):
        return None
    try:
        f = float(s)
    except ValueError:
        return None
    return f if f == f and f >= 0 else None


def station_id(state: str, city: str, name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", f"{city} {name}".lower()).strip("-")[:48]
    digest = hashlib.sha1(f"{state}|{city}|{name}".encode()).hexdigest()[:6]
    return f"{base}-{digest}"


def pivot(rows: list[dict]) -> list[dict]:
    """Rows (one per station per pollutant) -> one dict per station with pm25/pm10."""
    stations: dict[str, dict] = {}
    for r in rows:
        name = (r.get("station") or "").strip()
        city = (r.get("city") or "").strip()
        state = (r.get("state") or "").strip()
        if not name:
            continue
        lat, lon = _num(r.get("latitude")), _num(r.get("longitude"))
        if lat is None or lon is None or not bool(domain.in_domain(lat, lon)):
            continue
        pollutant = str(r.get("pollutant_id") or "").strip().lower()
        value = _num(r.get("avg_value", r.get("pollutant_avg")))
        try:
            observed = parse_cpcb_last_update(r.get("last_update", ""))
        except ValueError:
            continue
        sid = station_id(state, city, name)
        st = stations.setdefault(sid, {"id": sid, "name": name, "city": city, "state": state,
                                       "lat": lat, "lon": lon, "pm25": None, "pm10": None,
                                       "observedAt": iso_z(observed), "provider": "CPCB",
                                       "tier": "reference", "source": "data.gov.in"})
        if pollutant in _PM25 and value is not None:
            st["pm25"] = value
            st["observedAt"] = iso_z(observed)
        elif pollutant in _PM10 and value is not None:
            st["pm10"] = value
    return sorted((s for s in stations.values() if s["pm25"] is not None), key=lambda s: s["id"])


def to_ddb_items(stations: list[dict], now: datetime | None = None) -> list[dict]:
    ttl = ttl_epoch(OBS_TTL_DAYS, now)
    items: list[dict] = []
    for s in stations:
        hour = iso_z(floor_hour(datetime.fromisoformat(s["observedAt"].replace("Z", "+00:00"))))
        items.append({"PK": ddb.station_pk(s["id"]), "SK": ddb.obs_sk(hour), "pm25": s["pm25"],
                      "pm10": s["pm10"], "lat": s["lat"], "lon": s["lon"], "city": s["city"],
                      "observedAt": s["observedAt"], "ttl": ttl})
        items.append({"PK": ddb.station_pk(s["id"]), "SK": "META", "name": s["name"], "city": s["city"],
                      "state": s["state"], "lat": s["lat"], "lon": s["lon"], "lastSeen": s["observedAt"]})
    return items


def _from_data_gov(api_key: str, now: datetime) -> tuple[list[dict], dict]:
    """(stations, diagnostics). Never raises: a dead host must not fail the whole ingest."""
    try:
        rows = fetch_rows(api_key)
    except (requests.RequestException, RuntimeError) as exc:
        detail = redact(exc)
        log.warning("data.gov.in unavailable, live layer is OpenAQ only: %s", detail)
        return [], {"ok": False, "error": detail[:200], "resourceId": RESOURCE_ID}
    storage().put_json(f"raw/cpcb/{now:%Y-%m-%d}/{now:%H}.json", rows)
    stations = pivot(rows)
    return stations, {"ok": True, "rows": len(rows), "stations": len(stations),
                      "resourceId": RESOURCE_ID}


def _from_openaq(api_key: str, now: datetime) -> tuple[list[dict], dict]:
    """(stations, diagnostics). Never raises, for the same reason as above."""
    from ingest_cpcb import openaq_live

    try:
        return openaq_live.fetch_stations(api_key, now)
    except (requests.RequestException, RuntimeError) as exc:
        detail = redact(exc)
        log.warning("openaq unavailable: %s", detail)
        return [], {"ok": False, "error": detail[:200]}


def run(now: datetime | None = None, api_key: str | None = None,
        openaq_key: str | None = None) -> dict:
    """Merge both station sources into live/cpcb/latest.json. Reference-grade wins on a tie."""
    now = now or utc_now()
    if not api_key and not openaq_key:
        log.warning("no DATA_GOV_API_KEY and no OPENAQ_API_KEY: station ingest skipped")
        return {"skipped": "no station api key", "fetchedAt": iso_z(now)}

    cpcb_stations, cpcb_diag = _from_data_gov(api_key, now) if api_key else ([], {"ok": False, "error": "no key"})
    oaq_stations, oaq_diag = _from_openaq(openaq_key, now) if openaq_key else ([], {"ok": False, "error": "no key"})

    # Reference monitors take precedence when both sources carry the same place.
    merged: dict[str, dict] = {s["id"]: s for s in oaq_stations}
    merged.update({s["id"]: s for s in cpcb_stations})
    stations = sorted(merged.values(), key=lambda s: s["id"])

    snapshot = {"fetchedAt": iso_z(now), "resourceId": RESOURCE_ID, "stations": stations,
                "sources": {"dataGovIn": cpcb_diag, "openaq": oaq_diag}}
    storage().put_json(LATEST_KEY, snapshot)
    written = ddb.put_items(to_ddb_items(stations, now))
    summary = {"fetchedAt": iso_z(now), "stations": len(stations), "ddbWritten": written,
               "byTier": {t: sum(1 for s in stations if s.get("tier") == t)
                          for t in sorted({s.get("tier", "?") for s in stations})},
               "sources": {"dataGovIn": cpcb_diag, "openaq": oaq_diag}}
    log.info("station ingest: %s", summary)
    return summary
