"""CPCB PM2.5 sub-index, bands and school protocol tiers (DESIGN.md §6.1, §6.2).

[VERIFY] breakpoints against the current CPCB National AQI document before shipping.
[VERIFY] tier -> GRAP stage mapping against the current CAQM GRAP schedule.
"""
from __future__ import annotations

from typing import NamedTuple


class Breakpoint(NamedTuple):
    c_lo: float
    c_hi: float
    i_lo: float
    i_hi: float
    band: str


# PM2.5 (ug/m3) -> sub-index. Concentrations above the last breakpoint are capped at 500.
PM25_BREAKPOINTS: tuple[Breakpoint, ...] = (
    Breakpoint(0, 30, 0, 50, "Good"),
    Breakpoint(30, 60, 51, 100, "Satisfactory"),
    Breakpoint(60, 90, 101, 200, "Moderate"),
    Breakpoint(90, 120, 201, 300, "Poor"),
    Breakpoint(120, 250, 301, 400, "Very Poor"),
    Breakpoint(250, 380, 401, 500, "Severe"),
)

# Colour ramp keyed to the CPCB PM2.5 bands (§5.8). Shared with the web legend via the manifest.
PM25_RAMP: tuple[tuple[float, str], ...] = (
    (30, "#9ED6A0"),   # satisfactory  (below 30 is transparent)
    (60, "#F7E07A"),   # moderate
    (90, "#F0A35E"),   # poor
    (120, "#D75B4A"),  # very poor
    (250, "#7C2B3F"),  # severe (250+)
)


def pm25_subindex(c: float) -> int:
    """Piecewise-linear CPCB sub-index for a PM2.5 concentration in ug/m3."""
    if c is None or c != c:  # None or NaN
        raise ValueError("concentration required")
    c = max(0.0, float(c))
    for bp in PM25_BREAKPOINTS:
        if c <= bp.c_hi:
            i = (bp.i_hi - bp.i_lo) / (bp.c_hi - bp.c_lo) * (c - bp.c_lo) + bp.i_lo
            return int(round(i))
    return 500


def band_for_aqi(aqi: float) -> str:
    for bp in PM25_BREAKPOINTS:
        if aqi <= bp.i_hi:
            return bp.band
    return "Severe"


class Tier(NamedTuple):
    id: str
    label: str
    aqi_max: float          # inclusive upper bound of the tier
    grap: str
    colour: str


# §6.2. T4 never says "close"; wording lives in the protocol engine (Day 3).
TIERS: tuple[Tier, ...] = (
    Tier("T0", "Normal", 200, "", "#3FA34D"),
    Tier("T1", "Caution", 300, "Stage I (Poor)", "#E0B13A"),
    Tier("T2", "Indoors", 400, "Stage II (Very Poor)", "#D9743B"),
    Tier("T3", "Restrict", 450, "Stage III (Severe)", "#B8383B"),
    Tier("T4", "Closure advisory", float("inf"), "Stage IV (Severe+)", "#6B1F3A"),
)


def tier_for_aqi(aqi: float) -> Tier:
    for t in TIERS:
        if aqi <= t.aqi_max:
            return t
    return TIERS[-1]


def tier_for_pm25(c: float) -> Tier:
    return tier_for_aqi(pm25_subindex(c))


def pm25_subindex_array(c):
    """Vectorised pm25_subindex with the same official band constants. Returns float array."""
    import numpy as np

    c = np.maximum(np.nan_to_num(np.asarray(c, dtype=np.float64)), 0.0)
    out = np.full(c.shape, 500.0)
    done = np.zeros(c.shape, dtype=bool)
    for bp in PM25_BREAKPOINTS:
        m = (~done) & (c <= bp.c_hi)
        out[m] = (bp.i_hi - bp.i_lo) / (bp.c_hi - bp.c_lo) * (c[m] - bp.c_lo) + bp.i_lo
        done |= m
    return np.round(out)


TIER_AQI_MAX = [t.aqi_max for t in TIERS[:-1]]  # 200, 300, 400, 450


def tier_index_array(aqi):
    """0..4 (T0..T4) for an array of AQI values."""
    import numpy as np

    return np.searchsorted(np.asarray(TIER_AQI_MAX, dtype=np.float64), np.asarray(aqi, dtype=np.float64), side="left")
