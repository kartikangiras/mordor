"""Forecast -> decision. Deliberately boring and fully auditable (DESIGN.md §6).

Tiers are anchored to CAQM GRAP stages [VERIFY current schedule]. T4 never says "close":
closure is a government decision, we only point the principal at the DoE order.
"""
from __future__ import annotations

from datetime import datetime

from common import domain
from common.timeutil import IST

TIER_ORDER = ("T0", "T1", "T2", "T3", "T4")
ACTIONS = ("pt_indoors", "windows_shut", "masks", "assembly_indoor")

PROTOCOL: dict[str, dict] = {
    "T0": {"outdoor": "Normal outdoor activity", "windows": "Normal", "masks": "Not needed",
           "assembly": "Outdoor OK", "grapAnchor": ""},
    "T1": {"outdoor": "Shorten PT to 20 minutes, no running drills", "windows": "Shut 11:00-16:00",
           "masks": "Offer to asthmatic students", "assembly": "Indoor", "grapAnchor": "Stage I (Poor)"},
    "T2": {"outdoor": "All outdoor activity cancelled", "windows": "Shut all day; purifier on if present",
           "masks": "Recommended for the bus queue", "assembly": "Indoor, shortened", "grapAnchor": "Stage II (Very Poor)"},
    "T3": {"outdoor": "Cancelled", "windows": "Shut all day", "masks": "Distribute at the gate",
           "assembly": "Cancelled", "grapAnchor": "Stage III (Severe)"},
    "T4": {"outdoor": "Cancelled", "windows": "Shut all day", "masks": "Distribute at the gate",
           "assembly": "Cancelled", "grapAnchor": "Stage IV (Severe+)",
           "advisory": "Stage IV conditions are forecast. Check for a Directorate of Education order and prepare for online classes."},
}
DEFAULT_ACTIONS: dict[str, list[str]] = {
    "T0": [], "T1": ["windows_shut", "assembly_indoor"], "T2": list(ACTIONS), "T3": list(ACTIONS), "T4": list(ACTIONS),
}
STRIP_START, STRIP_END = "08:00", "16:00"   # the card's window strip spans the school day incl. dismissal


def _hhmm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def _clock(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _spoken(minutes: int) -> str:
    """'10 am', '3:30 pm' for headlines."""
    h, m = divmod(minutes, 60)
    ampm = "am" if h < 12 else "pm"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d} {ampm}" if m else f"{h12} {ampm}"


def tier_rank(t: str | None) -> int:
    return TIER_ORDER.index(t) if t in TIER_ORDER else -1


def hour_in_windows(minute_of_day: int, school_hours=domain.SCHOOL_HOURS_IST, dismissal=domain.DISMISSAL_IST) -> bool:
    return (_hhmm(school_hours[0]) <= minute_of_day < _hhmm(school_hours[1])
            or _hhmm(dismissal[0]) <= minute_of_day < _hhmm(dismissal[1]))


def _ist(t_iso: str) -> datetime:
    return datetime.fromisoformat(t_iso.replace("Z", "+00:00")).astimezone(IST)


def windows_for_day(hourly: list[dict], date_ist: str, strip: tuple[str, str] = (STRIP_START, STRIP_END)) -> list[dict]:
    """Contiguous same-tier spans across the strip on `date_ist`.
    Each hourly row: {"t": iso utc, "tier": "T0".."T4", "aqi": int}."""
    rows = []
    for r in hourly:
        if r.get("tier") is None:
            continue
        ti = _ist(r["t"])
        if ti.strftime("%Y-%m-%d") != date_ist:
            continue
        m = ti.hour * 60 + ti.minute
        if _hhmm(strip[0]) <= m < _hhmm(strip[1]):
            rows.append((m, r["tier"], r.get("aqi")))
    rows.sort()
    spans: list[dict] = []
    for m, tier, aqi in rows:
        if spans and spans[-1]["tier"] == tier and _hhmm(spans[-1]["toIst"]) == m:
            spans[-1]["toIst"] = _clock(m + 60)
            spans[-1]["peakAqi"] = max(spans[-1]["peakAqi"] or 0, aqi or 0)
        else:
            spans.append({"fromIst": _clock(m), "toIst": _clock(m + 60), "tier": tier, "peakAqi": aqi})
    return spans


def day_tier(windows: list[dict], school_hours=domain.SCHOOL_HOURS_IST, dismissal=domain.DISMISSAL_IST) -> str | None:
    """Max tier over spans that overlap school hours or the dismissal window."""
    best = None
    for w in windows:
        a, b = _hhmm(w["fromIst"]), _hhmm(w["toIst"])
        overlaps = any(hour_in_windows(m, school_hours, dismissal) for m in range(a, b, 60))
        if overlaps and tier_rank(w["tier"]) > tier_rank(best):
            best = w["tier"]
    return best


def first_hour_at_or_above(windows: list[dict], tier: str) -> int | None:
    for w in windows:
        if tier_rank(w["tier"]) >= tier_rank(tier):
            return _hhmm(w["fromIst"])
    return None


def headline(windows: list[dict], tier: str | None, actor: str = "school") -> str:
    if tier is None:
        return "Forecast not yet calibrated: no tier for today."
    if actor == "rwa":
        return _headline_rwa(tier)
    if actor == "hospital":
        return _headline_hospital(tier)
    if tier == "T0":
        return "Normal day. Outdoor activity as usual."
    start = first_hour_at_or_above(windows, "T2" if tier_rank(tier) >= 2 else "T1")
    first = _hhmm(windows[0]["fromIst"]) if windows else _hhmm(STRIP_START)
    # hours land on :30 IST (runs are on the UTC hour); the first window of the day is "from the start"
    when = "" if start is None or start <= max(_hhmm(STRIP_START), first) else f" after {_spoken(start)}"
    if tier == "T1":
        return f"Shorten PT to 20 minutes{when}; no running drills."
    if tier == "T2":
        return f"Cancel outdoor games{when}. Keep windows shut."
    if tier == "T3":
        return f"Cancel outdoor activity and assembly{when}. Masks at the gate."
    return PROTOCOL["T4"]["advisory"]


def _headline_rwa(tier: str) -> str:
    if tier == "T0":
        return "Normal day. Parks and walks as usual."
    if tier == "T1":
        return "Shorten the evening play hour; elderly residents advised to stay in."
    if tier == "T2":
        return "Pause morning walks and evening play. Gensets off, elderly residents indoors."
    if tier == "T3":
        return "Shut the park gates. Gensets off. Door-to-door notice for elderly residents."
    return "Stage IV conditions are forecast. Park gates shut; watch for CAQM orders on work from home and vehicles."


def _headline_hospital(tier: str) -> str:
    if tier == "T0":
        return "Normal day. Routine respiratory load."
    if tier == "T1":
        return "Expect more asthma visits; check inhaler and nebuliser stock."
    if tier == "T2":
        return "Respiratory and emergency wards on alert. Top up oxygen and nebulisers; hold beds for asthma and COPD."
    if tier == "T3":
        return "Wards on alert with extra evening staff. Oxygen verified; beds held."
    return "Stage IV conditions are forecast. Wards on alert round the clock; beds held; helpline staffed."


def outdoor_hours_cancelled(windows: list[dict], school_hours=domain.SCHOOL_HOURS_IST, dismissal=domain.DISMISSAL_IST) -> float:
    """School-window hours at T2 or worse: the 'outdoor hours avoided' impact number (§8 /api/impact)."""
    total = 0.0
    for w in windows:
        if tier_rank(w["tier"]) < 2:
            continue
        for m in range(_hhmm(w["fromIst"]), _hhmm(w["toIst"]), 60):
            if hour_in_windows(m, school_hours, dismissal):
                total += 1.0
    return total


MIN_WINDOW_HOURS_AHEAD = 3


def pick_date(hourly: list[dict], school_hours=domain.SCHOOL_HOURS_IST, dismissal=domain.DISMISSAL_IST) -> str | None:
    """The date the card is for: the first IST date in the horizon with at least
    MIN_WINDOW_HOURS_AHEAD school-window hours still ahead, so an afternoon run points the
    principal at tomorrow rather than at the last hour of today."""
    counts: dict[str, int] = {}
    for r in hourly:
        ti = _ist(r["t"])
        if hour_in_windows(ti.hour * 60 + ti.minute, school_hours, dismissal):
            counts[ti.strftime("%Y-%m-%d")] = counts.get(ti.strftime("%Y-%m-%d"), 0) + 1
    for d in sorted(counts):
        if counts[d] >= MIN_WINDOW_HOURS_AHEAD:
            return d
    return next(iter(sorted(counts)), None)


def build_card(hourly: list[dict], date_ist: str | None = None, school_hours=domain.SCHOOL_HOURS_IST,
               dismissal=domain.DISMISSAL_IST, has_purifiers: bool = False, actor: str = "school") -> dict:
    """Everything an exposure card needs except the message and the entity's contacts.
    `school_hours`/`dismissal` are the first two windows of concern for any exposure actor."""
    from protocol.actors import actor_type

    at = actor_type(actor)
    date_ist = date_ist or pick_date(hourly, school_hours, dismissal)
    strip = (min(school_hours[0], dismissal[0]), max(school_hours[1], dismissal[1])) if actor != "school" else (STRIP_START, STRIP_END)
    windows = windows_for_day(hourly, date_ist, strip) if date_ist else []
    tier = day_tier(windows, school_hours, dismissal) if windows else None
    proto = dict(at["protocol"].get(tier, {})) if tier else None
    if proto and actor == "school" and tier == "T2" and not has_purifiers:
        proto["windows"] = "Shut all day"
    peak = max((w["peakAqi"] or 0 for w in windows), default=None)
    return {
        "actorType": actor, "kind": at["kind"], "date": date_ist, "dayTier": tier, "windows": windows, "protocol": proto,
        "headline": headline(windows, tier, actor), "defaultActions": at["defaultActions"].get(tier or "T0", []),
        "actions": at["actions"], "anchor": at["anchor"], "strip": list(strip),
        "peakAqi": peak, "outdoorHoursCancelled": outdoor_hours_cancelled(windows, school_hours, dismissal) if windows else 0.0,
        "schoolHoursIst": list(school_hours), "dismissalIst": list(dismissal), "hasPurifiers": has_purifiers,
    }


def build_source_card(cells: list[dict], date_ist: str, district: str, actor: str = "agri_officer") -> dict:
    """The district agriculture officer's card: the cells most likely to burn in the next 48 h."""
    from protocol.actors import actor_type

    at = actor_type(actor)
    top = sorted(cells, key=lambda c: -c["score"])[:8]
    burning = [c for c in cells if c.get("fires24", 0) > 0]
    worst = top[0]["category"] if top else "Low"
    n_extreme = sum(1 for c in top if c["category"] == "Extreme")
    n_high = sum(1 for c in top if c["category"] == "High")
    if not top:
        head = f"No burning-risk cells in {district} in the next 48 hours."
    else:
        parts = []
        if n_extreme:
            parts.append(f"{n_extreme} cell{'s' if n_extreme > 1 else ''} at Extreme risk")
        if n_high:
            parts.append(f"{n_high} at High")
        head = f"{district}: {', '.join(parts) if parts else 'risk is Moderate or Low'}; {len(burning)} cell{'s' if len(burning) != 1 else ''} already burning."
    return {
        "actorType": actor, "kind": at["kind"], "date": date_ist, "dayTier": worst, "district": district,
        "cells": top, "burningNow": len(burning), "headline": head, "defaultActions": at["defaultActions"].get(worst, []),
        "actions": at["actions"], "anchor": at["anchor"], "protocol": None, "windows": [], "peakAqi": None,
        "outdoorHoursCancelled": 0.0,
    }
