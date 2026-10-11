"""Binning particles to the output grid and the boundary-layer dilution (DESIGN.md §5.6)."""
from __future__ import annotations

import numpy as np

from common import domain

_CELL_AREA = domain.cell_area_grid().astype(np.float64)


def bin_mass(lat, lon, mass) -> np.ndarray:
    """(NLAT, NLON) column mass per cell. Points outside the domain are ignored."""
    lat = np.asarray(lat)
    lon = np.asarray(lon)
    mass = np.asarray(mass, dtype=np.float64)
    m = domain.in_domain(lat, lon)
    i_lat, i_lon = domain.cell_index(lat[m], lon[m])
    flat = np.bincount(i_lat * domain.NLON + i_lon, weights=mass[m], minlength=domain.NLAT * domain.NLON)
    return flat.reshape(domain.NLAT, domain.NLON)


def raw_surface(mass_grid: np.ndarray, blh_grid: np.ndarray, blh_floor: float = domain.BLH_FLOOR_M) -> np.ndarray:
    """Column mass -> surface 'raw' field: mass / (cell_area * max(BLH, floor)). Multiplying by the
    fitted k gives ug/m3 (§5.6, §5.7). Kept separate so k can be applied at render time."""
    return (mass_grid / (_CELL_AREA * np.maximum(blh_grid, blh_floor))).astype(np.float32)


def to_concentration(raw: np.ndarray, k: float) -> np.ndarray:
    return (k * raw).astype(np.float32)
