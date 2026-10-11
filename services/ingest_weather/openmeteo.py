"""Open-Meteo winds, boundary-layer height and CAMS PM2.5 background (DESIGN.md §4.2).

One call fetches all WIND_NLAT x WIND_NLON grid nodes (verified 2026-09-26). Output is packed
as dense [time][lat][lon] arrays so the forecast can index it without parsing per point:

  wind.json: {lats, lons, times, u925, v925, u10, v10, blh, ...}
  aq.json:   {lats, lons, times, pm25, pm10, ...}

Speeds are m/s; u is eastward, v is northward; null where the model has no value.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime

import requests

from common import ddb, domain
from common.storage import storage
from common.timeutil import iso_z, run_id, utc_now

log = logging.getLogger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
WIND_VARS = ("wind_speed_925hPa", "wind_direction_925hPa", "wind_speed_10m", "wind_direction_10m",
             "boundary_layer_height", "precipitation")
AQ_VARS = ("pm2_5", "pm10", "nitrogen_dioxide")   # NO2 = the traffic tracer for the zones view
PAST_DAYS = 1       # spin-up (§5.2)
FORECAST_DAYS = 3   # 48 h horizon + slack
TIMEOUT = 90
LATEST_KEY = "raw/openmeteo/latest.json"


def grid_points() -> list[tuple[float, float]]:
    """Row-major (lat outer, lon inner) to match the packed arrays."""
    return [(float(la), float(lo)) for la in domain.wind_lats() for lo in domain.wind_lons()]


def _coord_params(points: list[tuple[float, float]]) -> dict:
    return {
        "latitude": ",".join(f"{la:.2f}" for la, _ in points),
        "longitude": ",".join(f"{lo:.2f}" for _, lo in points),
    }


def fetch_wind(session: requests.Session | None = None, points=None) -> list[dict]:
    points = points or grid_points()
    params = {
        **_coord_params(points),
        "hourly": ",".join(WIND_VARS),
        "past_days": PAST_DAYS,
        "forecast_days": FORECAST_DAYS,
        "timezone": "UTC",
        "wind_speed_unit": "ms",
    }
    resp = (session or requests).get(FORECAST_URL, params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else [data]


def fetch_aq(session: requests.Session | None = None, points=None) -> list[dict]:
    points = points or grid_points()
    params = {
        **_coord_params(points),
        "hourly": ",".join(AQ_VARS),
        "past_days": PAST_DAYS,
        "forecast_days": FORECAST_DAYS,
        "timezone": "UTC",
    }
    resp = (session or requests).get(AQ_URL, params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else [data]


def to_uv(speed, direction) -> tuple[float | None, float | None]:
    """Meteorological direction (where the wind comes FROM) -> eastward u, northward v."""
    if speed is None or direction is None:
        return None, None
    rad = math.radians(direction)
    return round(-speed * math.sin(rad), 3), round(-speed * math.cos(rad), 3)


def _times(point: dict) -> list[str]:
    return [t if t.endswith("Z") else t + ":00Z" if len(t) == 16 else t + "Z" for t in point["hourly"]["time"]]


def _pack(points_data: list[dict], n_lat: int, n_lon: int, fields: dict[str, callable]) -> dict:
    """fields: name -> fn(hourly_dict, t_index) -> value. Builds [T][n_lat][n_lon] arrays."""
    if len(points_data) != n_lat * n_lon:
        raise ValueError(f"expected {n_lat * n_lon} points, got {len(points_data)}")
    times = _times(points_data[0])
    n_t = len(times)
    out = {name: [[[None] * n_lon for _ in range(n_lat)] for _ in range(n_t)] for name in fields}
    for idx, p in enumerate(points_data):
        i_lat, i_lon = divmod(idx, n_lon)
        h = p["hourly"]
        if len(h["time"]) != n_t:
            raise ValueError("inconsistent time axes across points")
        for name, fn in fields.items():
            arr = out[name]
            for t in range(n_t):
                arr[t][i_lat][i_lon] = fn(h, t)
    return {"times": times, **out}


def pack_wind(points_data: list[dict]) -> dict:
    def u925(h, t):
        return to_uv(h["wind_speed_925hPa"][t], h["wind_direction_925hPa"][t])[0]

    def v925(h, t):
        return to_uv(h["wind_speed_925hPa"][t], h["wind_direction_925hPa"][t])[1]

    def u10(h, t):
        return to_uv(h["wind_speed_10m"][t], h["wind_direction_10m"][t])[0]

    def v10(h, t):
        return to_uv(h["wind_speed_10m"][t], h["wind_direction_10m"][t])[1]

    def blh(h, t):
        return h.get("boundary_layer_height", [None] * (t + 1))[t]

    def precip(h, t):
        return h.get("precipitation", [None] * (t + 1))[t]

    packed = _pack(points_data, domain.WIND_NLAT, domain.WIND_NLON,
                   {"u925": u925, "v925": v925, "u10": u10, "v10": v10, "blh": blh, "precip": precip})
    packed["blhAvailable"] = any(v is not None for layer in packed["blh"] for row in layer for v in row)
    return {"lats": domain.wind_lats().tolist(), "lons": domain.wind_lons().tolist(), "units": "m/s, blh m, precip mm/h",
            "source": "open-meteo forecast (925 hPa + 10 m)", **packed}


def pack_aq(points_data: list[dict]) -> dict:
    packed = _pack(points_data, domain.WIND_NLAT, domain.WIND_NLON,
                   {"pm25": lambda h, t: h["pm2_5"][t], "pm10": lambda h, t: h["pm10"][t],
                    "no2": lambda h, t: h.get("nitrogen_dioxide", [None] * (t + 1))[t]})
    return {"lats": domain.wind_lats().tolist(), "lons": domain.wind_lons().tolist(), "units": "ug/m3",
            "source": "CAMS global via open-meteo air-quality", **packed}


def run(now: datetime | None = None) -> dict:
    now = now or utc_now()
    fetch_id = run_id(now)
    sess = requests.Session()
    wind = pack_wind(fetch_wind(sess))
    aq = pack_aq(fetch_aq(sess))
    wind["fetchedAt"] = aq["fetchedAt"] = iso_z(now)
    wind_key, aq_key = f"raw/openmeteo/{fetch_id}/wind.json", f"raw/openmeteo/{fetch_id}/aq.json"
    storage().put_json(wind_key, wind)
    storage().put_json(aq_key, aq)
    pointer = {"id": fetch_id, "fetchedAt": iso_z(now), "windKey": wind_key, "aqKey": aq_key,
               "hours": len(wind["times"]), "from": wind["times"][0], "to": wind["times"][-1],
               "blhAvailable": wind["blhAvailable"]}
    storage().put_json(LATEST_KEY, pointer)
    ddb.put_item({"PK": ddb.INGEST_PK, "SK": f"WEATHER#{fetch_id}", **pointer})
    log.info("weather ingest: %s", pointer)
    return pointer


def load_latest_from(store) -> tuple[dict, dict, dict]:
    """(wind, aq, pointer) for the most recent fetch in `store`, or raises."""
    pointer = store.get_json(LATEST_KEY)
    if not pointer:
        raise FileNotFoundError("no weather ingest yet - run ingest_weather first")
    wind = store.get_json(pointer["windKey"])
    aq = store.get_json(pointer["aqKey"])
    if wind is None or aq is None:
        raise FileNotFoundError(f"weather files for {pointer['id']} missing")
    return wind, aq, pointer


def load_latest() -> tuple[dict, dict, dict]:
    return load_latest_from(storage())


# ------------------------------------------------------------------ archives (hindcast, §13.1)
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
# Verified 2026-09-26: the ERA5 archive has no pressure-level winds; 100 m is the transport proxy.
ARCHIVE_WIND_VARS = ("wind_speed_100m", "wind_direction_100m", "wind_speed_10m", "wind_direction_10m",
                     "boundary_layer_height")
ARCHIVE_CHUNK = 39


def _chunked(points, chunk):
    for i in range(0, len(points), chunk):
        yield points[i:i + chunk]


def fetch_archive_wind(start: str, end: str, session: requests.Session | None = None, points=None) -> list[dict]:
    points = points or grid_points()
    out: list[dict] = []
    for part in _chunked(points, ARCHIVE_CHUNK):
        params = {**_coord_params(part), "start_date": start, "end_date": end,
                  "hourly": ",".join(ARCHIVE_WIND_VARS), "timezone": "UTC", "wind_speed_unit": "ms"}
        resp = (session or requests).get(ARCHIVE_URL, params=params, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        out.extend(data if isinstance(data, list) else [data])
    return out


def pack_archive_wind(points_data: list[dict]) -> dict:
    """Same layout as pack_wind, with the 100 m wind standing in for 925 hPa."""
    def u100(h, t):
        return to_uv(h["wind_speed_100m"][t], h["wind_direction_100m"][t])[0]

    def v100(h, t):
        return to_uv(h["wind_speed_100m"][t], h["wind_direction_100m"][t])[1]

    def u10(h, t):
        return to_uv(h["wind_speed_10m"][t], h["wind_direction_10m"][t])[0]

    def v10(h, t):
        return to_uv(h["wind_speed_10m"][t], h["wind_direction_10m"][t])[1]

    def blh(h, t):
        return h.get("boundary_layer_height", [None] * (t + 1))[t]

    packed = _pack(points_data, domain.WIND_NLAT, domain.WIND_NLON,
                   {"u925": u100, "v925": v100, "u10": u10, "v10": v10, "blh": blh})
    packed["blhAvailable"] = any(v is not None for layer in packed["blh"] for row in layer for v in row)
    return {"lats": domain.wind_lats().tolist(), "lons": domain.wind_lons().tolist(), "units": "m/s, blh m",
            "source": "ERA5 archive via open-meteo (100 m + 10 m; no 925 hPa in the archive)",
            "windLevel": "100m", **packed}


def fetch_archive_aq_points(points: list[tuple[float, float]], start: str, end: str,
                            session: requests.Session | None = None) -> list[dict]:
    """CAMS PM2.5 history at arbitrary points (e.g. stations). Returns one dict per point."""
    out: list[dict] = []
    for part in _chunked(points, ARCHIVE_CHUNK):
        params = {**_coord_params(part), "start_date": start, "end_date": end, "hourly": "pm2_5", "timezone": "UTC"}
        resp = (session or requests).get(AQ_URL, params=params, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        out.extend(data if isinstance(data, list) else [data])
    return out
