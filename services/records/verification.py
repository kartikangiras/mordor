"""Step 6, Verify: was the day as bad as the card said, at the nearest station? Observations
come from DynamoDB (CPCB via data.gov.in, when the key exists) or, keyless, from the OpenAQ
open-data archive, which lags about four days - so a verification can stay 'pending'."""
from __future__ import annotations

import csv
import gzip
import io
import json
import logging
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from common import aqi, ddb
from common.timeutil import IST
from protocol.rules import _hhmm, tier_rank

log = logging.getLogger(__name__)
OPENAQ = "https://openaq-data-archive.s3.amazonaws.com/records/csv.gz/locationid={id}/year={y}/month={m}/location-{id}-{ymd}.csv.gz"


def nearest_station(lat: float, lon: float, index_path: str = "data/openaq_stations.json", max_km: float = 25.0) -> dict | None:
    try:
        idx = json.loads(Path(index_path).read_text())["stations"]
    except (OSError, ValueError, KeyError):
        return None
    best, best_d = None, 1e9
    for s in idx:
        d = math.hypot((s["lat"] - lat) * 111.32, (s["lon"] - lon) * 111.32 * math.cos(math.radians(lat)))
        if d < best_d:
            best, best_d = s, d
    if best and best_d <= max_km:
        return {"id": best["id"], "name": best["name"], "lat": best["lat"], "lon": best["lon"], "distanceKm": round(best_d, 1), "source": "openaq-archive"}
    return None


def observed_hours_openaq(station_id: int, date_ist: str, session: requests.Session | None = None) -> dict[str, float] | None:
    """{iso_utc_hour: pm25} for the IST date; None when the archive has no file yet."""
    sess = session or requests.Session()
    day = datetime.strptime(date_ist, "%Y-%m-%d")
    out: dict[str, float] = {}
    found = False
    for d in (day - timedelta(days=1), day, day + timedelta(days=1)):   # IST day spans two UTC-named files
        r = sess.get(OPENAQ.format(id=station_id, y=d.year, m=f"{d.month:02d}", ymd=d.strftime("%Y%m%d")), timeout=30)
        if r.status_code != 200:
            continue
        found = True
        for row in csv.DictReader(io.StringIO(gzip.decompress(r.content).decode())):
            if row.get("parameter") != "pm25":
                continue
            try:
                t = datetime.fromisoformat(row["datetime"]).astimezone(timezone.utc)
                v = float(row["value"])
            except (ValueError, KeyError):
                continue
            if t.astimezone(IST).strftime("%Y-%m-%d") == date_ist and 0 <= v <= 1000:
                out[t.strftime("%Y-%m-%dT%H:%M:%SZ")] = v
    return out if found else None


def observed_hours_ddb(lat: float, lon: float, date_ist: str) -> tuple[dict | None, dict[str, float]]:
    """CPCB observations ingested hourly (STATION#/OBS#) - needs the data.gov.in key upstream."""
    if not ddb.enabled():
        return None, {}
    # the station index lives in the live snapshot; without it we cannot pick a station
    return None, {}


def assess(card: dict, hours: dict[str, float], windows: list[list[str]]) -> dict:
    """Compare the forecast tier with the observed tier inside the entity's windows of concern."""
    in_win = {}
    for t, v in hours.items():
        ti = datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(IST)
        m = ti.hour * 60 + ti.minute
        if any(_hhmm(a) <= m < _hhmm(b) for a, b in windows):
            in_win[t] = v
    if not in_win:
        return {"outcome": "pending", "reason": "no observations inside the windows yet", "observed": None}
    peak = max(in_win.values())
    obs_aqi = aqi.pm25_subindex(peak)
    obs_tier = aqi.tier_for_aqi(obs_aqi).id
    hours_t2 = sum(1 for v in in_win.values() if tier_rank(aqi.tier_for_aqi(aqi.pm25_subindex(v)).id) >= 2)
    fc = card.get("dayTier")
    if fc is None:
        outcome = "moot"
    elif tier_rank(fc) >= 2 and tier_rank(obs_tier) >= 2:
        outcome = "confirmed"
    elif tier_rank(fc) >= 2:
        outcome = "not_confirmed"
    elif tier_rank(obs_tier) >= 2:
        outcome = "missed"
    else:
        outcome = "moot"
    return {"outcome": outcome, "observed": {"peakPm25": round(peak, 1), "peakAqi": obs_aqi, "tier": obs_tier, "hoursAtT2plus": hours_t2,
                                             "hoursObserved": len(in_win)}, "forecast": {"tier": fc, "peakAqi": card.get("peakAqi")}}
