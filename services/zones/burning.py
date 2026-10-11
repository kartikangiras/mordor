"""Active burning areas and a 48-hour burning-risk score (Hestia's RiskScoreOracle idea,
re-aimed at stubble fires). Everything is keyless and every component is listed per cell.

Cells are 0.25 deg (~27 km). Score 0-100:
  recent activity   0-35  detections in the last 48 h, scaled to the 95th percentile cell
  trend             0-15  last 24 h vs the 24 h before
  season climatology 0-25 what this cell did on these dates in 2024 (FIRMS S-NPP archive)
  vegetation change 0-15  NDVI drop over the last two 8-day composites (harvest / burn signal)
  rain in next 48 h -10-0 forecast precipitation suppresses burning
Categories as in Hestia: Low 0-25, Moderate 26-50, High 51-75, Extreme 76-100.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

import numpy as np

from common import domain
from common.timeutil import ensure_utc

log = logging.getLogger(__name__)

CELL = 0.25
NLON = int(round((domain.LON_MAX - domain.LON_MIN) / CELL))  # 24
NLAT = int(round((domain.LAT_MAX - domain.LAT_MIN) / CELL))  # 22

# Gazetteer for naming a burning cell, and the definition of the focus region: the five
# states the product is about (Punjab, Haryana, Delhi, Rajasthan, Uttar Pradesh, plus
# Chandigarh). Pakistani Punjab towns were removed on 2026-10-07 — a cell there must not
# be captioned with an Indian district. Fire DETECTIONS are still read across the whole
# domain, because smoke from across the border genuinely reaches Delhi; only the named,
# displayed cells are restricted. See domain.in_focus_states.
TOWNS = [("Amritsar", 31.63, 74.87), ("Tarn Taran", 31.45, 74.93), ("Gurdaspur", 32.04, 75.40), ("Pathankot", 32.27, 75.65),
         ("Jalandhar", 31.33, 75.58), ("Kapurthala", 31.38, 75.38), ("Hoshiarpur", 31.53, 75.91), ("Ludhiana", 30.90, 75.86),
         ("Moga", 30.82, 75.17), ("Firozpur", 30.93, 74.61), ("Faridkot", 30.67, 74.76), ("Muktsar", 30.47, 74.52),
         ("Bathinda", 30.21, 74.95), ("Mansa", 29.99, 75.39), ("Sangrur", 30.25, 75.84), ("Barnala", 30.37, 75.55),
         ("Patiala", 30.34, 76.39), ("Fatehgarh Sahib", 30.64, 76.39), ("Rupnagar", 30.97, 76.53), ("Mohali", 30.70, 76.72),
         ("Chandigarh", 30.73, 76.78), ("Ambala", 30.38, 76.78), ("Yamunanagar", 30.13, 77.29), ("Kurukshetra", 29.97, 76.88),
         ("Kaithal", 29.80, 76.40), ("Karnal", 29.69, 76.99), ("Panipat", 29.39, 76.97), ("Jind", 29.32, 76.31),
         ("Fatehabad", 29.52, 75.46), ("Sirsa", 29.53, 75.03), ("Hisar", 29.15, 75.72), ("Rohtak", 28.89, 76.59),
         ("Sonipat", 28.99, 77.02), ("Delhi", 28.61, 77.21), ("Meerut", 28.98, 77.71), ("Muzaffarnagar", 29.47, 77.70),
         ("Saharanpur", 29.97, 77.55), ("Bijnor", 29.37, 78.14), ("Moradabad", 28.84, 78.78), ("Bulandshahr", 28.41, 77.85),
         ("Aligarh", 27.88, 78.08), ("Mathura", 27.49, 77.67), ("Alwar", 27.55, 76.63), ("Bikaner", 28.02, 73.31),
         ("Sri Ganganagar", 29.92, 73.88), ("Hanumangarh", 29.58, 74.33), ("Abohar", 30.14, 74.20), ("Fazilka", 30.40, 74.03),
         ("Malerkotla", 30.52, 75.88), ("Nabha", 30.37, 76.15), ("Rajpura", 30.48, 76.59), ("Samrala", 30.84, 76.19),
         ("Phillaur", 31.02, 75.79), ("Nawanshahr", 31.12, 76.12), ("Zira", 30.97, 74.99), ("Jagraon", 30.79, 75.47),
         ("Dhuri", 30.37, 75.87), ("Sunam", 30.13, 75.80), ("Tohana", 29.71, 75.90), ("Narwana", 29.60, 76.12),
         ("Pehowa", 29.98, 76.58), ("Shahabad", 30.17, 76.87), ("Batala", 31.82, 75.20), ("Dasuya", 31.82, 75.65),
         ("Khanna", 30.70, 76.22), ("Sirhind", 30.64, 76.38), ("Ellenabad", 29.45, 74.66), ("Rania", 29.53, 74.83),
         ("Bhiwani", 28.79, 76.14), ("Jhajjar", 28.61, 76.66)]


def cell_of(lat, lon):
    i = np.floor((np.asarray(lat) - domain.LAT_MIN) / CELL).astype(int)
    j = np.floor((np.asarray(lon) - domain.LON_MIN) / CELL).astype(int)
    return i, j


def cell_bounds(i: int, j: int) -> list[list[float]]:
    s, w = domain.LAT_MIN + i * CELL, domain.LON_MIN + j * CELL
    return [[w, s], [w + CELL, s], [w + CELL, s + CELL], [w, s + CELL], [w, s]]


def in_focus(lat: float, lon: float) -> bool:
    """Is this cell inside the five states the product covers? (domain.in_focus_states)"""
    return domain.in_focus_states(lat, lon)


def nearest_town(lat: float, lon: float) -> str:
    best = min(TOWNS, key=lambda t: (t[1] - lat) ** 2 + ((t[2] - lon) * np.cos(np.radians(lat))) ** 2)
    d = np.hypot((best[1] - lat) * 111.32, (best[2] - lon) * 111.32 * np.cos(np.radians(lat)))
    return best[0] if d < 20 else f"near {best[0]}"


def counts_grid(fires: list[dict], t_from: datetime, t_to: datetime) -> tuple[np.ndarray, np.ndarray]:
    """(count, frp_sum) on the 0.25 deg grid for detections in [t_from, t_to)."""
    cnt = np.zeros((NLAT, NLON))
    frp = np.zeros((NLAT, NLON))
    lo, hi = ensure_utc(t_from).strftime("%Y-%m-%dT%H:%M:%SZ"), ensure_utc(t_to).strftime("%Y-%m-%dT%H:%M:%SZ")
    for f in fires:
        if lo <= f["acqUtc"] < hi and bool(domain.in_domain(f["lat"], f["lon"])):
            i, j = cell_of(f["lat"], f["lon"])
            cnt[i, j] += 1
            frp[i, j] += float(f.get("frp") or 0)
    return cnt, frp


def climatology(table: dict | None, now: datetime, window_days: int = 7) -> np.ndarray | None:
    """Mean daily detections per cell on the same calendar dates in 2024 (+/- window_days) from
    the committed table (static/climatology_2024.json, built by tools/build_climatology.py)."""
    if not table:
        return None
    days = table["days"]
    counts = np.asarray(table["counts"], dtype=np.float64)
    want = {(datetime(2024, now.month, now.day) + timedelta(days=d)).strftime("%Y-%m-%d") for d in range(-window_days, window_days + 1)}
    idx = [n for n, d in enumerate(days) if d in want]
    if not idx:
        return None
    return counts[idx].mean(axis=0)


def category(score: float) -> str:
    return "Low" if score <= 25 else "Moderate" if score <= 50 else "High" if score <= 75 else "Extreme"


def burn_risk(fires48: list[dict], now: datetime, clim: np.ndarray | None, ndvi_change: np.ndarray | None,
              rain48: np.ndarray | None) -> dict:
    """GeoJSON of every cell with activity or risk, plus the top burning areas."""
    c24, f24 = counts_grid(fires48, now - timedelta(hours=24), now)
    c48, f48 = counts_grid(fires48, now - timedelta(hours=48), now)
    prev24 = c48 - c24
    p95 = max(float(np.percentile(c48[c48 > 0], 95)) if (c48 > 0).any() else 1.0, 1.0)
    clim_p95 = max(float(np.percentile(clim[clim > 0], 95)) if clim is not None and (clim > 0).any() else 1.0, 1.0)
    features, areas = [], []
    for i in range(NLAT):
        for j in range(NLON):
            recent = 35.0 * min(1.0, c48[i, j] / p95)
            trend = 15.0 * float(np.clip((c24[i, j] - prev24[i, j]) / max(prev24[i, j], 2.0), -1, 1)) if c48[i, j] > 0 else 0.0
            trend = max(0.0, trend) if c24[i, j] >= prev24[i, j] else trend * 0.5
            season = 25.0 * min(1.0, clim[i, j] / clim_p95) if clim is not None else 0.0
            veg = 0.0
            if ndvi_change is not None and not np.isnan(ndvi_change[i, j]):
                veg = 15.0 * float(np.clip(-ndvi_change[i, j] / 0.15, 0, 1))   # a 0.15 NDVI drop = full score
            rain = -10.0 * min(1.0, float(rain48[i, j]) / 5.0) if rain48 is not None else 0.0   # 5 mm = full suppression
            score = float(np.clip(recent + trend + season + veg + rain, 0, 100))
            if c48[i, j] == 0 and score < 10:
                continue
            lat_c, lon_c = domain.LAT_MIN + (i + 0.5) * CELL, domain.LON_MIN + (j + 0.5) * CELL
            if not in_focus(lat_c, lon_c):
                continue   # outside Punjab / Haryana / Delhi / Rajasthan / UP: not displayed
            props = {"i": i, "j": j, "name": nearest_town(lat_c, lon_c), "fires24": int(c24[i, j]), "fires48": int(c48[i, j]),
                     "frp24": round(float(f24[i, j]), 1), "trend": int(c24[i, j] - prev24[i, j]),
                     "climatologyPerDay": round(float(clim[i, j]), 1) if clim is not None else None,
                     "ndviChange": round(float(ndvi_change[i, j]), 3) if ndvi_change is not None and not np.isnan(ndvi_change[i, j]) else None,
                     "rain48mm": round(float(rain48[i, j]), 1) if rain48 is not None else None,
                     "score": round(score), "category": category(score),
                     "components": {"recent": round(recent), "trend": round(trend), "season": round(season), "vegetation": round(veg), "rain": round(rain)}}
            features.append({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [cell_bounds(i, j)]}, "properties": props})
            if c24[i, j] > 0:
                areas.append({**props, "lat": round(lat_c, 3), "lon": round(lon_c, 3)})
    areas.sort(key=lambda a: (-a["fires24"], -a["frp24"]))
    risk_top = sorted((f["properties"] for f in features), key=lambda p: -p["score"])[:8]
    return {
        "type": "FeatureCollection", "generatedFor": ensure_utc(now).strftime("%Y-%m-%dT%H:%M:%SZ"), "cellDeg": CELL,
        "method": "score 0-100 = recent activity (0-35) + trend (0-15) + 2024 season climatology (0-25) + NDVI drop (0-15) - rain (0-10); "
                  "Low <=25, Moderate <=50, High <=75, Extreme >75. Statistical, not a fire-behaviour model.",
        "inputs": {"fires48": len(fires48), "climatology": clim is not None, "ndvi": ndvi_change is not None, "rain": rain48 is not None},
        "topBurning": areas[:8], "topRisk": [{k: v for k, v in p.items() if k != "components"} for p in risk_top],
        "features": features,
    }
