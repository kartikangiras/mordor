"""THE grid and domain constants. Imported by the ingest, forecast, renderer and API so the
domain is defined exactly once (DESIGN.md §5.1, §11, §18). Never duplicate these numbers.

Array convention used everywhere downstream:
    grid[i_lat, i_lon]  with i_lat = 0 at LAT_MIN (south) and i_lon = 0 at LON_MIN (west).
The renderer flips vertically so that PNG row 0 is the north edge.
"""
from __future__ import annotations

import numpy as np

# --- spatial domain (W, S, E, N) ------------------------------------------------------------
# Covers the five states the product serves - Punjab, Haryana, Delhi, Rajasthan (north) and
# western Uttar Pradesh, plus Chandigarh - and reaches past the western border on purpose,
# because stubble smoke from Pakistani Punjab is advected into the NCR. Fires are read across
# the whole box; stations, exposure zones and named burning cells are restricted to the focus
# states (see ingest_cpcb/openaq_live.py FOCUS_COUNTRIES and zones/burning.py FOCUS_MAX_KM).
LON_MIN, LON_MAX = 73.0, 79.0
LAT_MIN, LAT_MAX = 27.0, 32.5
DOMAIN_WSEN = (LON_MIN, LAT_MIN, LON_MAX, LAT_MAX)

# --- focus region: the five states, i.e. the domain east of the international border --------
# The domain reaches into Pakistani Punjab on purpose (fires there blow into the NCR), but
# stations, exposure zones and named burning cells must stay inside Punjab, Haryana, Delhi,
# Rajasthan, UP and Chandigarh. Distance to the nearest Indian town cannot decide this —
# Lahore is only ~48 km from Amritsar — so this is the Radcliffe Line as a polyline of
# (latitude, border longitude), anchored on the actual crossings: Sialkot/Jammu sector,
# Wagah-Attari (31.60, 74.57), Hussainiwala (30.95, 74.53), Sadqi/Fazilka (30.40),
# Hindumalkot (29.86, 73.57). Below ~29 N the border runs west of LON_MIN, so the whole
# in-domain strip is India.
_BORDER_LON_BY_LAT = [
    (27.00, 73.00), (29.00, 73.00), (29.86, 73.57), (30.40, 73.95),
    (30.95, 74.53), (31.60, 74.57), (32.10, 74.95), (32.50, 75.05),
]


def border_lon(lat: float) -> float:
    """Longitude of the international border at this latitude (linear between anchors)."""
    pts = _BORDER_LON_BY_LAT
    if lat <= pts[0][0]:
        return pts[0][1]
    if lat >= pts[-1][0]:
        return pts[-1][1]
    for (la0, lo0), (la1, lo1) in zip(pts, pts[1:], strict=False):
        if la0 <= lat <= la1:
            f = (lat - la0) / (la1 - la0)
            return lo0 + f * (lo1 - lo0)
    return pts[-1][1]


def in_focus_states(lat: float, lon: float) -> bool:
    """Inside the five states the product serves (and inside the domain)."""
    return bool(in_domain(lat, lon)) and lon >= border_lon(lat)

# Output (concentration) grid: 0.05 deg ~ 5.5 km
DLON = DLAT = 0.05
NLON = int(round((LON_MAX - LON_MIN) / DLON))  # 120
NLAT = int(round((LAT_MAX - LAT_MIN) / DLAT))  # 110

# Wind sampling grid: 0.5 deg nodes, inclusive of both edges
WIND_DLON = WIND_DLAT = 0.5
WIND_NLON = int(round((LON_MAX - LON_MIN) / WIND_DLON)) + 1  # 13
WIND_NLAT = int(round((LAT_MAX - LAT_MIN) / WIND_DLAT)) + 1  # 12

# Corners for a MapLibre `image` source: top-left, top-right, bottom-right, bottom-left.
IMAGE_CORNERS = [[LON_MIN, LAT_MAX], [LON_MAX, LAT_MAX], [LON_MAX, LAT_MIN], [LON_MIN, LAT_MIN]]

# --- timebase and particle model --------------------------------------------------------------
FORECAST_HOURS = 48
# Particles from fires detected up to 24 h ago have already travelled; the run starts
# 24 h before "now" so they are where the wind put them, not sitting on the fire (§5.2).
SPINUP_HOURS = 24
SUBSTEP_SECONDS = 1800
PARTICLES_PER_H = 20
BURN_WINDOW_H = 3
MAX_PARTICLES = 400_000

K_H_M2_S = 5.0e3       # horizontal eddy diffusivity, tunable
TAU_HOURS = 48.0       # lumped loss timescale, tunable
BLH_FLOOR_M = 100.0
WIND_BLEND_925 = 0.7   # remainder from 10 m

IST_OFFSET_MIN = 330
SCHOOL_HOURS_IST = ("08:00", "14:00")
DISMISSAL_IST = ("15:00", "16:00")

# Fitted in §5.7 by the hindcast; never hardcode a guess. None means "uncalibrated":
# the renderer then draws relative units and says so in the manifest.
K_SCALE: float | None = None

M_PER_DEG_LAT = 111_320.0


def grid_lats() -> np.ndarray:
    """Cell-centre latitudes, south to north."""
    return LAT_MIN + (np.arange(NLAT) + 0.5) * DLAT


def grid_lons() -> np.ndarray:
    """Cell-centre longitudes, west to east."""
    return LON_MIN + (np.arange(NLON) + 0.5) * DLON


def wind_lats() -> np.ndarray:
    return LAT_MIN + np.arange(WIND_NLAT) * WIND_DLAT


def wind_lons() -> np.ndarray:
    return LON_MIN + np.arange(WIND_NLON) * WIND_DLON


def m_per_deg_lon(lat) -> np.ndarray:
    return M_PER_DEG_LAT * np.cos(np.radians(lat))


def cell_area_m2(lat) -> np.ndarray:
    """Area of one output cell at latitude `lat` (metres squared)."""
    return (DLAT * M_PER_DEG_LAT) * (DLON * m_per_deg_lon(lat))


def cell_area_grid() -> np.ndarray:
    """(NLAT, NLON) array of cell areas."""
    return np.repeat(cell_area_m2(grid_lats())[:, None], NLON, axis=1)


def in_domain(lat, lon) -> np.ndarray:
    lat = np.asarray(lat)
    lon = np.asarray(lon)
    return (lat >= LAT_MIN) & (lat < LAT_MAX) & (lon >= LON_MIN) & (lon < LON_MAX)


def cell_index(lat, lon) -> tuple[np.ndarray, np.ndarray]:
    """Integer (i_lat, i_lon) for points; caller must mask with in_domain first."""
    i_lat = np.floor((np.asarray(lat) - LAT_MIN) / DLAT).astype(np.int64)
    i_lon = np.floor((np.asarray(lon) - LON_MIN) / DLON).astype(np.int64)
    return i_lat, i_lon


def describe() -> dict:
    """The domain as it is exported in manifest.json so the web app never hardcodes it."""
    return {
        "wsen": list(DOMAIN_WSEN),
        "dlat": DLAT,
        "dlon": DLON,
        "nlat": NLAT,
        "nlon": NLON,
        "imageCorners": IMAGE_CORNERS,
    }
