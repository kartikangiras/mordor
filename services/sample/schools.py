"""Per-school exposure from a finished run (DESIGN.md §6.3, §7.1, §8).

For every school point: fire increment at its cell (k x raw), CAMS background (bilinear),
total, CPCB sub-index and tier per hour; then per IST date the *day tier* = max tier during
school hours (08:00-14:00) plus the dismissal window (15:00-16:00). The map layer gets one
feature per named school; DynamoDB gets the full hourly series for every school (7 d TTL).

Uncalibrated runs (k is None) produce no tiers: a tier from the background alone would be a
lie about the fires, so the layer says calibrated=false and the UI greys the schools.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime

import numpy as np

from common import aqi, domain
from common.timeutil import IST, iso_z, ttl_epoch
from forecast.run import RunResult
from forecast.wind import background_points
from protocol import interval, rules

FC_TTL_DAYS = 7


def _hhmm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def in_school_window(t_ist: datetime, school_hours=domain.SCHOOL_HOURS_IST, dismissal=domain.DISMISSAL_IST) -> bool:
    m = t_ist.hour * 60 + t_ist.minute
    return _hhmm(school_hours[0]) <= m < _hhmm(school_hours[1]) or _hhmm(dismissal[0]) <= m < _hhmm(dismissal[1])


def _point_features(schools: dict) -> list[dict]:
    out = []
    for f in schools.get("features", []):
        g = f.get("geometry") or {}
        if g.get("type") != "Point":
            continue
        lon, lat = g["coordinates"][:2]
        if not bool(domain.in_domain(lat, lon)):
            continue
        out.append(f)
    return out


def sample_schools(result: RunResult, aq_json: dict, schools: dict, k: float | None, rid: str,
                   now: datetime | None = None, school_meta: dict | None = None,
                   calibration: dict | None = None) -> tuple[dict, list[dict], dict, dict]:
    """Returns (layer geojson, ddb items, summary, cards) where cards maps onboarded/demo school ids to
    their public protocol card (no contacts)."""
    feats = _point_features(schools)
    n = len(feats)
    hours = result.hours
    hours_ist = [h.astimezone(IST) for h in hours]
    window = np.array([in_school_window(t) for t in hours_ist])
    cards: dict[str, dict] = {}
    if n == 0:
        return ({"type": "FeatureCollection", "features": [], "runId": rid, "calibrated": k is not None},
                [], {"count": 0, "calibrated": k is not None}, cards)
    lat = np.array([f["geometry"]["coordinates"][1] for f in feats])
    lon = np.array([f["geometry"]["coordinates"][0] for f in feats])
    i_lat, i_lon = domain.cell_index(lat, lon)
    raw = result.raw[:, i_lat, i_lon]                      # (H, N)
    bg = background_points(aq_json, lat, lon, hours)       # (H, N)
    fire = raw * k if k is not None else None
    total = bg + fire if fire is not None else None
    aqi_arr = aqi.pm25_subindex_array(total) if total is not None else None
    tier_idx = aqi.tier_index_array(aqi_arr) if aqi_arr is not None else None

    # per IST date, which hour indices fall in the school window
    dates: dict[str, list[int]] = {}
    for h, t in enumerate(hours_ist):
        if window[h]:
            dates.setdefault(t.strftime("%Y-%m-%d"), []).append(h)
    ordered_dates = sorted(dates)
    ttl = ttl_epoch(FC_TTL_DAYS, now)

    features, items = [], []
    tier_counter: Counter = Counter()
    for j, f in enumerate(feats):
        props = f.get("properties", {})
        sid = props.get("id") or f.get("id") or f"school-{j}"
        days = []
        for d in ordered_dates:
            idx = dates[d]
            if tier_idx is None:
                days.append({"date": d, "tier": None, "peakAqi": None, "peakHourIst": None})
                continue
            sub = idx[int(np.argmax(aqi_arr[idx, j]))]
            days.append({"date": d, "tier": aqi.TIERS[int(tier_idx[idx, j].max())].id,
                         "peakAqi": int(aqi_arr[sub, j]), "peakHourIst": hours_ist[sub].strftime("%H:%M")})
        day = days[0] if days else {"date": None, "tier": None, "peakAqi": None, "peakHourIst": None}
        hourly = []
        for h in range(len(hours)):
            row = {"t": iso_z(hours[h]), "pm25Background": round(float(bg[h, j]), 1)}
            if fire is not None:
                pm = float(total[h, j])
                row.update({"pm25Fire": round(float(fire[h, j]), 1), "pm25Total": round(pm, 1),
                            "aqi": int(aqi_arr[h, j]), "tier": aqi.TIERS[int(tier_idx[h, j])].id})
                interval.attach_band(row, pm, calibration, h)   # lead = forecast hour index
            else:
                row["fireRaw"] = float(raw[h, j])
            hourly.append(row)
        meta = (school_meta or {}).get(sid) or {}
        sh = tuple(meta.get("hours") or domain.SCHOOL_HOURS_IST)
        dm = tuple(meta.get("dismissal") or domain.DISMISSAL_IST)
        card = rules.build_card(hourly, school_hours=sh, dismissal=dm,
                                has_purifiers=bool(meta.get("hasPurifiers"))) if k is not None else None
        interval.attach_card_extras(card, hourly, sh, dm)
        item = {"PK": f"SCHOOL#{sid}", "SK": f"FC#{rid}", "runId": rid, "dayTier": day["tier"],
                "dayDate": day["date"], "days": days, "hourly": hourly, "calibrated": k is not None, "ttl": ttl}
        if card:
            item.update({"date": card["date"], "windows": card["windows"], "protocol": card["protocol"],
                         "headline": card["headline"], "defaultActions": card["defaultActions"], "peakAqi": card["peakAqi"],
                         "outdoorHoursCancelled": card["outdoorHoursCancelled"], "schoolHoursIst": card["schoolHoursIst"],
                         "dismissalIst": card["dismissalIst"], "hasPurifiers": card["hasPurifiers"],
                         # interval + dose ride along with the item so the public card and
                         # /api/me/forecast both see them (they are built from this dict)
                         "interval": card.get("interval"), "dose": card.get("dose")})
        items.append(item)
        if props.get("onboarded") or props.get("demo"):
            public_card = {k2: v2 for k2, v2 in item.items() if k2 not in ("PK", "SK", "ttl")}
            public_card.update({"schoolId": sid, "name": props.get("name"), "name_hi": props.get("name_hi"),
                                "demo": bool(props.get("demo")), "onboarded": bool(props.get("onboarded"))})
            if card and card["dayTier"]:
                from notify import fallback

                public_card["message"] = fallback.render(props.get("name") or sid, card["date"], card["dayTier"],
                                                         card["windows"], card["peakAqi"], card["dismissalIst"])
            cards[sid] = public_card
        if props.get("name"):
            tier_counter[day["tier"] or "uncalibrated"] += 1
            features.append({"type": "Feature", "geometry": f["geometry"], "properties": {
                "id": sid, "name": props.get("name"), "name_hi": props.get("name_hi"),
                "dayTier": day["tier"], "dayDate": day["date"], "peakAqi": day["peakAqi"],
                "peakHourIst": day["peakHourIst"], "days": days, "demo": bool(props.get("demo")),
                "onboarded": bool(props.get("onboarded"))}})
    layer = {"type": "FeatureCollection", "runId": rid, "calibrated": k is not None,
             "schoolHoursIst": list(domain.SCHOOL_HOURS_IST), "dismissalIst": list(domain.DISMISSAL_IST),
             "features": features}
    summary = {"count": n, "named": len(features), "calibrated": k is not None, "byTier": dict(tier_counter),
               "dayDate": ordered_dates[0] if ordered_dates else None, "cards": sorted(cards)}
    return layer, items, summary, cards
