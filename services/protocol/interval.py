"""Prediction intervals and inhaled dose: the two numbers a card needs beyond a point value.

**Intervals.** `tools/hindcast.py` writes split-conformal half-widths (ug/m3) into
`validation/latest/calibration.json`; this module turns one into a concentration band and the
matching CPCB sub-index band. R2 says how much variance the model explains; the half-width says
how wrong a single hour is likely to be, which is the thing a principal is actually relying on
(DESIGN.md 13.2a, R4). The half-width is lead-dependent, so hours 25-48 get the wider one.

**Dose.** A concentration is not a decision variable; an inhaled mass is. Dose over an hour is
concentration x breathing rate, so the same AQI is a very different exposure for a child sitting
in a classroom and the same child running at games. Keeping the arithmetic explicit also keeps
it honest: we only integrate hours the forecast covers, we assume outdoor air with **no indoor
infiltration**, and we never convert mass into a health outcome - that would need
concentration-response functions and a population baseline we do not have.
"""
from __future__ import annotations

from datetime import datetime

from common import aqi
from common.timeutil import IST

#: Breathing rates in m3/h. Order-of-magnitude values for a school-age child at the three
#: activity levels that matter here, consistent with the ranges in the EPA Exposure Factors
#: Handbook (children 6-11 sit near 0.3-0.5 at rest and 1.0-1.4 at moderate exertion). They are
#: approximate by construction and are published alongside the dose for exactly that reason;
#: `ACTIVITY` is the knob, not a hidden constant.
ACTIVITY = {"rest": 0.35, "light": 0.60, "moderate": 1.20}

#: What a child is assumed to be doing during each window of the card.
SCHOOL_ACTIVITY = "light"        # in class, moving between rooms
DISMISSAL_ACTIVITY = "moderate"  # waiting outside, walking home, the gate crush
OUTSIDE_ACTIVITY = "rest"        # any other forecast hour: not claimed, not counted


def half_width(cal: dict | None, lead_h: int, level: str = "q90") -> float | None:
    """Conformal half-width in ug/m3 for a forecast hour `lead_h` ahead, or None."""
    if not cal:
        return None
    by_lead = cal.get("conformalByLead") or {}
    bucket = by_lead.get("lead01_24" if lead_h <= 24 else "lead25_48") or {}
    v = bucket.get(level)
    if v is None:
        v = (cal.get("conformal") or {}).get(level)
    return float(v) if v is not None else None


def pm25_band(pm25: float, half: float | None) -> tuple[float, float] | None:
    """(lo, hi) concentration band, clipped at zero. None when no half-width is available."""
    if half is None:
        return None
    return round(max(0.0, pm25 - half), 1), round(pm25 + half, 1)


def aqi_band(pm25: float, half: float | None) -> tuple[int, int] | None:
    """The band as CPCB sub-index values, so the card can show a tier range."""
    band = pm25_band(pm25, half)
    if band is None:
        return None
    return aqi.pm25_subindex(band[0]), aqi.pm25_subindex(band[1])


def hour_dose_ug(pm25: float, activity: str) -> float:
    """Inhaled PM2.5 mass over one hour, in micrograms, at a given activity level."""
    return float(pm25) * ACTIVITY.get(activity, ACTIVITY["rest"])


def activity_for(in_school: bool, in_dismissal: bool) -> str:
    if in_dismissal:
        return DISMISSAL_ACTIVITY
    if in_school:
        return SCHOOL_ACTIVITY
    return OUTSIDE_ACTIVITY


def dose_for_day(rows: list[dict]) -> dict | None:
    """Inhaled dose across the hours of one card.

    Each row: {"pm25": float, "hourIst": "HH:MM", "inSchool": bool, "inDismissal": bool}.
    Returns totals in micrograms plus the single worst hour, which is the actionable part: if
    one activity can be moved, this is the one to move.
    """
    counted = [r for r in rows if r.get("inSchool") or r.get("inDismissal")]
    if not counted:
        return None
    per_hour = []
    for r in counted:
        act = activity_for(bool(r.get("inSchool")), bool(r.get("inDismissal")))
        per_hour.append({"hourIst": r["hourIst"], "pm25": round(float(r["pm25"]), 1),
                         "activity": act, "ug": round(hour_dose_ug(r["pm25"], act), 1)})
    total = sum(h["ug"] for h in per_hour)
    school = sum(h["ug"] for h in per_hour if h["activity"] == SCHOOL_ACTIVITY)
    dismissal = sum(h["ug"] for h in per_hour if h["activity"] == DISMISSAL_ACTIVITY)
    worst = max(per_hour, key=lambda h: h["ug"])
    return {
        "totalUg": round(total, 1),
        "schoolHoursUg": round(school, 1),
        "dismissalUg": round(dismissal, 1),
        "dismissalShare": round(dismissal / total, 3) if total > 0 else None,
        "hours": len(per_hour),
        "worstHour": worst,
        "worstHourShare": round(worst["ug"] / total, 3) if total > 0 else None,
        "breathingRatesM3PerH": dict(ACTIVITY),
        "basis": "outdoor PM2.5 x breathing rate, school hours and dismissal only; "
                 "no indoor infiltration assumed; mass inhaled, not a health outcome",
    }


# ----------------------------------------------------------------- card-level attachment
# Both card builders (sample/schools.py for the map's schools, sample/entities.py for the demo
# and onboarded actors) construct hourly rows and call rules.build_card. They must attach the
# same things the same way, or - as happened on 2026-10-07 - the entity card overwrites the
# school card for a shared id and the bands silently vanish from what is served.

def _hhmm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def _ist(row: dict) -> datetime:
    return datetime.fromisoformat(row["t"].replace("Z", "+00:00")).astimezone(IST)


def attach_band(row: dict, pm25: float, cal: dict | None, lead_h: int) -> None:
    """Add pm25Lo/Hi, aqiLo/Hi and halfWidth to one hourly row, when a half-width exists."""
    half = half_width(cal, lead_h)
    band = pm25_band(pm25, half)
    if band is None:
        return
    ab = aqi_band(pm25, half)
    row.update({"pm25Lo": band[0], "pm25Hi": band[1], "aqiLo": ab[0], "aqiHi": ab[1], "halfWidth": half})


def dose_for_card(hourly: list[dict], date_ist: str, school_hours, dismissal) -> dict | None:
    """Inhaled dose for the card's day from its hourly rows (see dose_for_day)."""
    rows = []
    for row in hourly:
        if row.get("pm25Total") is None:
            continue
        t = _ist(row)
        if t.strftime("%Y-%m-%d") != date_ist:
            continue
        m = t.hour * 60 + t.minute
        rows.append({"pm25": row["pm25Total"], "hourIst": t.strftime("%H:%M"),
                     "inSchool": _hhmm(school_hours[0]) <= m < _hhmm(school_hours[1]),
                     "inDismissal": _hhmm(dismissal[0]) <= m < _hhmm(dismissal[1])})
    return dose_for_day(rows)


def peak_interval(hourly: list[dict], date_ist: str, school_hours, dismissal) -> dict | None:
    """The band around the worst hour of concern, so the card states a range, not a point."""
    best = None
    for row in hourly:
        if row.get("pm25Total") is None or row.get("pm25Lo") is None:
            continue
        t = _ist(row)
        if t.strftime("%Y-%m-%d") != date_ist:
            continue
        m = t.hour * 60 + t.minute
        if not (_hhmm(school_hours[0]) <= m < _hhmm(school_hours[1])
                or _hhmm(dismissal[0]) <= m < _hhmm(dismissal[1])):
            continue
        if best is None or row["pm25Total"] > best["pm25Total"]:
            best = row
    if best is None:
        return None
    return {"hourIst": _ist(best).strftime("%H:%M"),
            "pm25": best["pm25Total"], "pm25Lo": best["pm25Lo"], "pm25Hi": best["pm25Hi"],
            "aqi": best["aqi"], "aqiLo": best["aqiLo"], "aqiHi": best["aqiHi"],
            "halfWidth": best.get("halfWidth"), "level": "q90",
            "basis": "split-conformal 90% half-width on held-out hindcast residuals"}


def attach_card_extras(card: dict, hourly: list[dict], school_hours, dismissal) -> None:
    """Put `dose` and `interval` on a built card. No-op without a date (uncalibrated run)."""
    if not card or not card.get("date"):
        return
    card["dose"] = dose_for_card(hourly, card["date"], school_hours, dismissal)
    card["interval"] = peak_interval(hourly, card["date"], school_hours, dismissal)
