"""Exposure zones: the cities people live in, ranked by what the air is doing now and what it
does next (modelled on Hestia's treatment zones, applied to smoke exposure instead of fuel).

Per zone and per run: CAMS background PM2.5 (which already contains traffic and industry),
our stubble-fire increment, the total, the CPCB sub-index and tier, the stubble share at the
peak, hours until the plume arrives, and NO2 from CAMS as the traffic tracer. Nothing here is
attributed to traffic by assumption: NO2 is shown as a tracer, labelled as such.

Populations are approximate (2011 census urban agglomerations, rounded) and only used to
order ties and size circles - never as a claim.
"""
from __future__ import annotations

import numpy as np

from common import aqi, domain
from forecast.run import RunResult
from forecast.wind import _aq_arrays, _aq_slice, bilinear

# name, lat, lon, radius_km, approx population, state
# Focus region (2026-10-07): Delhi, Haryana, Uttar Pradesh, Punjab, Rajasthan and Chandigarh.
# Lahore was removed with the rest of the Pakistani places; fire detections across the border
# still feed the plume, but we do not publish exposure for cities we do not serve.
ZONES: list[dict] = [
    {"id": "delhi", "name": "Delhi", "name_hi": "दिल्ली", "lat": 28.61, "lon": 77.21, "radiusKm": 22, "population": 16_800_000, "region": "Delhi"},
    {"id": "gurugram", "name": "Gurugram", "name_hi": "गुरुग्राम", "lat": 28.46, "lon": 77.03, "radiusKm": 10, "population": 900_000, "region": "Haryana"},
    {"id": "faridabad", "name": "Faridabad", "name_hi": "फ़रीदाबाद", "lat": 28.41, "lon": 77.31, "radiusKm": 10, "population": 1_400_000, "region": "Haryana"},
    {"id": "ghaziabad", "name": "Ghaziabad", "name_hi": "ग़ाज़ियाबाद", "lat": 28.67, "lon": 77.42, "radiusKm": 10, "population": 1_650_000, "region": "Uttar Pradesh"},
    {"id": "noida", "name": "Noida", "name_hi": "नोएडा", "lat": 28.57, "lon": 77.33, "radiusKm": 9, "population": 650_000, "region": "Uttar Pradesh"},
    {"id": "meerut", "name": "Meerut", "name_hi": "मेरठ", "lat": 28.98, "lon": 77.71, "radiusKm": 9, "population": 1_300_000, "region": "Uttar Pradesh"},
    {"id": "panipat", "name": "Panipat", "name_hi": "पानीपत", "lat": 29.39, "lon": 76.97, "radiusKm": 7, "population": 300_000, "region": "Haryana"},
    {"id": "karnal", "name": "Karnal", "name_hi": "करनाल", "lat": 29.69, "lon": 76.99, "radiusKm": 7, "population": 300_000, "region": "Haryana"},
    {"id": "rohtak", "name": "Rohtak", "name_hi": "रोहतक", "lat": 28.89, "lon": 76.59, "radiusKm": 7, "population": 375_000, "region": "Haryana"},
    {"id": "hisar", "name": "Hisar", "name_hi": "हिसार", "lat": 29.15, "lon": 75.72, "radiusKm": 7, "population": 300_000, "region": "Haryana"},
    {"id": "chandigarh", "name": "Chandigarh", "name_hi": "चंडीगढ़", "lat": 30.73, "lon": 76.78, "radiusKm": 10, "population": 1_025_000, "region": "Chandigarh"},
    {"id": "ludhiana", "name": "Ludhiana", "name_hi": "लुधियाना", "lat": 30.90, "lon": 75.86, "radiusKm": 10, "population": 1_600_000, "region": "Punjab"},
    {"id": "jalandhar", "name": "Jalandhar", "name_hi": "जालंधर", "lat": 31.33, "lon": 75.58, "radiusKm": 8, "population": 870_000, "region": "Punjab"},
    {"id": "amritsar", "name": "Amritsar", "name_hi": "अमृतसर", "lat": 31.63, "lon": 74.87, "radiusKm": 9, "population": 1_130_000, "region": "Punjab"},
    {"id": "patiala", "name": "Patiala", "name_hi": "पटियाला", "lat": 30.34, "lon": 76.39, "radiusKm": 7, "population": 405_000, "region": "Punjab"},
    {"id": "bathinda", "name": "Bathinda", "name_hi": "बठिंडा", "lat": 30.21, "lon": 74.95, "radiusKm": 7, "population": 285_000, "region": "Punjab"},
]

ARRIVAL_THRESHOLD = 30.0  # ug/m3 of fire increment = "the plume has arrived"
NO2_BANDS = [(40, "low"), (90, "moderate"), (120, "high"), (230, "very high")]  # EU index bands, ug/m3


def _cells_within(lat: float, lon: float, radius_km: float) -> tuple[np.ndarray, np.ndarray]:
    glat, glon = np.meshgrid(domain.grid_lats(), domain.grid_lons(), indexing="ij")
    dy = (glat - lat) * 111.32
    dx = (glon - lon) * 111.32 * np.cos(np.radians(lat))
    m = np.hypot(dx, dy) <= radius_km
    if not m.any():  # tiny radius: at least the containing cell
        i_lat, i_lon = domain.cell_index(lat, lon)
        m[i_lat, i_lon] = True
    return np.nonzero(m)


def no2_band(v: float | None) -> str | None:
    if v is None:
        return None
    for lim, label in NO2_BANDS:
        if v < lim:
            return label
    return "extreme"


def zone_summaries(result: RunResult, aq_json: dict, k: float | None) -> dict:
    """runs/{runId}/zones.json: every zone's now/peak numbers plus two rankings."""
    hours = result.hours
    lats, lons, times, pm, step = _aq_arrays(aq_json)
    has_no2 = bool(aq_json.get("no2"))
    no2_arr = None
    if has_no2:
        from forecast.wind import _to_array

        no2_arr = _to_array(aq_json["no2"])
    out = []
    for z in ZONES:
        if not bool(domain.in_domain(z["lat"], z["lon"])):
            continue
        ii, jj = _cells_within(z["lat"], z["lon"], z["radiusKm"])
        raw_zone = result.raw[:, ii, jj].mean(axis=1)                       # (H+1,) area mean
        fire = raw_zone * k if k is not None else None
        bg = np.array([bilinear(_aq_slice(pm, times, step, t), lats, lons, [z["lat"]], [z["lon"]])[0] for t in hours])
        no2 = (np.array([bilinear(_aq_slice(no2_arr, times, step, t), lats, lons, [z["lat"]], [z["lon"]])[0] for t in hours])
               if no2_arr is not None else None)
        total = bg + fire if fire is not None else None
        aqi_s = aqi.pm25_subindex_array(total) if total is not None else aqi.pm25_subindex_array(bg)
        tiers = aqi.tier_index_array(aqi_s)
        peak_h = int(np.argmax(total if total is not None else bg))
        arrival = next((h for h in range(len(hours)) if fire is not None and fire[h] >= ARRIVAL_THRESHOLD), None)
        rec = {
            **{k2: z[k2] for k2 in ("id", "name", "name_hi", "lat", "lon", "radiusKm", "population", "region")},
            "calibrated": k is not None,
            "now": {"pm25Background": round(float(bg[0]), 1), "pm25Fire": round(float(fire[0]), 1) if fire is not None else None,
                    "pm25Total": round(float(total[0]), 1) if total is not None else None, "aqi": int(aqi_s[0]),
                    "tier": aqi.TIERS[int(tiers[0])].id, "no2": round(float(no2[0]), 1) if no2 is not None else None,
                    "no2Band": no2_band(float(no2[0])) if no2 is not None else None},
            "peak": {"hour": peak_h, "t": hours[peak_h].strftime("%Y-%m-%dT%H:%M:%SZ"),
                     "pm25Background": round(float(bg[peak_h]), 1), "pm25Fire": round(float(fire[peak_h]), 1) if fire is not None else None,
                     "pm25Total": round(float(total[peak_h]), 1) if total is not None else None, "aqi": int(aqi_s[peak_h]),
                     "tier": aqi.TIERS[int(tiers[peak_h])].id,
                     "stubbleShare": round(float(fire[peak_h] / total[peak_h]), 2) if total is not None and total[peak_h] > 0 else None,
                     "no2": round(float(no2[peak_h]), 1) if no2 is not None else None},
            "arrivalHour": arrival, "arrivalT": hours[arrival].strftime("%Y-%m-%dT%H:%M:%SZ") if arrival is not None else None,
            "hourly": {"pm25Fire": [round(float(v), 1) for v in fire] if fire is not None else None,
                       "pm25Background": [round(float(v), 1) for v in bg],
                       "no2": [round(float(v), 1) for v in no2] if no2 is not None else None},
            "worstTier": aqi.TIERS[int(tiers.max())].id,
        }
        out.append(rec)
    rank_now = sorted(out, key=lambda r: (-(r["now"]["pm25Total"] or r["now"]["pm25Background"]), -r["population"]))
    rank_peak = sorted(out, key=lambda r: (-(r["peak"]["pm25Total"] or r["peak"]["pm25Background"]), -r["population"]))
    return {
        "runId": result.run_id, "hours": [h.strftime("%Y-%m-%dT%H:%M:%SZ") for h in hours], "calibrated": k is not None,
        "arrivalThreshold": ARRIVAL_THRESHOLD,
        "note": "Background = CAMS (includes traffic, industry, dust). Fire = our stubble increment. NO2 = CAMS, "
                "shown as a traffic tracer, not as an attributed share. Populations approximate.",
        "rankingNow": [r["id"] for r in rank_now], "rankingPeak": [r["id"] for r in rank_peak],
        "zones": out,
    }
