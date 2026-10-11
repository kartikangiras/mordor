"""Wind and boundary-layer interpolation (DESIGN.md §5.1, §5.4, §5.6).

Takes the packed wind.json from ingest_weather and answers two questions, vectorised:
  * what is the effective (blended 925 hPa / 10 m) wind at these particle positions, now?
  * what is the boundary-layer height on the output grid, at this hour?
Bilinear in space, linear in time. No scipy.
"""
from __future__ import annotations

import math
from datetime import datetime

import numpy as np

from common import domain
from common.timeutil import IST, ensure_utc


def _parse_times(times: list[str]) -> list[datetime]:
    return [datetime.fromisoformat(t.replace("Z", "+00:00")) for t in times]


def _to_array(nested, fill_forward: bool = True) -> np.ndarray:
    """[T][lat][lon] with None -> float32 array, gaps filled along time (forward then backward)."""
    arr = np.array([[[np.nan if v is None else v for v in row] for row in layer] for layer in nested],
                   dtype=np.float32)
    if fill_forward and arr.ndim == 3:
        for t in range(1, arr.shape[0]):
            m = np.isnan(arr[t])
            arr[t][m] = arr[t - 1][m]
        for t in range(arr.shape[0] - 2, -1, -1):
            m = np.isnan(arr[t])
            arr[t][m] = arr[t + 1][m]
    return arr


def bilinear(field: np.ndarray, lats: np.ndarray, lons: np.ndarray, qlat, qlon) -> np.ndarray:
    """Sample a regular (lat, lon) grid at query points; clamps outside the grid."""
    qlat = np.asarray(qlat, dtype=np.float64)
    qlon = np.asarray(qlon, dtype=np.float64)
    dlat = lats[1] - lats[0]
    dlon = lons[1] - lons[0]
    fy = np.clip((qlat - lats[0]) / dlat, 0, len(lats) - 1 - 1e-9)
    fx = np.clip((qlon - lons[0]) / dlon, 0, len(lons) - 1 - 1e-9)
    iy = np.floor(fy).astype(np.int64)
    ix = np.floor(fx).astype(np.int64)
    wy = fy - iy
    wx = fx - ix
    iy1 = np.minimum(iy + 1, len(lats) - 1)
    ix1 = np.minimum(ix + 1, len(lons) - 1)
    return ((1 - wy) * (1 - wx) * field[iy, ix] + (1 - wy) * wx * field[iy, ix1]
            + wy * (1 - wx) * field[iy1, ix] + wy * wx * field[iy1, ix1])


def blh_fallback(t: datetime) -> float:
    """Diurnal sinusoid in metres, keyed to IST hour (§5.6 fallback)."""
    hour = ensure_utc(t).astimezone(IST).hour + ensure_utc(t).astimezone(IST).minute / 60
    return 200.0 + 1600.0 * max(0.0, math.sin(math.pi * (hour - 6) / 12))


class WindField:
    def __init__(self, wind_json: dict, blend_925: float = domain.WIND_BLEND_925):
        self.lats = np.asarray(wind_json["lats"], dtype=np.float64)
        self.lons = np.asarray(wind_json["lons"], dtype=np.float64)
        self.times = _parse_times(wind_json["times"])
        self.t0 = self.times[0]
        step = (self.times[1] - self.times[0]).total_seconds()
        if any(abs((b - a).total_seconds() - step) > 1 for a, b in zip(self.times, self.times[1:], strict=False)):
            raise ValueError("wind time axis is not uniform")
        self.step_s = step
        u925, v925 = _to_array(wind_json["u925"]), _to_array(wind_json["v925"])
        u10, v10 = _to_array(wind_json["u10"]), _to_array(wind_json["v10"])
        self.u = np.nan_to_num(blend_925 * u925 + (1 - blend_925) * u10)
        self.v = np.nan_to_num(blend_925 * v925 + (1 - blend_925) * v10)
        self.blh = _to_array(wind_json.get("blh", [])) if wind_json.get("blh") else None
        self.blh_available = self.blh is not None and not np.isnan(self.blh).all()
        if self.blh is not None and self.blh_available:
            # any remaining NaN (a node the model never filled) -> mean of the slice
            for t in range(self.blh.shape[0]):
                m = np.isnan(self.blh[t])
                if m.any():
                    self.blh[t][m] = np.nanmean(self.blh[t]) if (~m).any() else np.nan
        self.source = wind_json.get("source", "")
        self.precip = _to_array(wind_json["precip"]) if wind_json.get("precip") else None

    # -- time --------------------------------------------------------------------------------
    def _tindex(self, t: datetime) -> tuple[int, float]:
        f = (ensure_utc(t) - self.t0).total_seconds() / self.step_s
        f = min(max(f, 0.0), len(self.times) - 1 - 1e-9)
        i = int(math.floor(f))
        return i, f - i

    def covers(self, t: datetime) -> bool:
        return self.times[0] <= ensure_utc(t) <= self.times[-1]

    # -- sampling ----------------------------------------------------------------------------
    def sample_uv(self, lat, lon, t: datetime) -> tuple[np.ndarray, np.ndarray]:
        i, w = self._tindex(t)
        j = min(i + 1, len(self.times) - 1)
        u = (1 - w) * bilinear(self.u[i], self.lats, self.lons, lat, lon) + w * bilinear(self.u[j], self.lats, self.lons, lat, lon)
        v = (1 - w) * bilinear(self.v[i], self.lats, self.lons, lat, lon) + w * bilinear(self.v[j], self.lats, self.lons, lat, lon)
        return u, v

    def blh_grid(self, t: datetime) -> np.ndarray:
        """(NLAT, NLON) boundary-layer height in metres on the output grid at time t."""
        if not self.blh_available:
            return np.full((domain.NLAT, domain.NLON), blh_fallback(t), dtype=np.float32)
        i, w = self._tindex(t)
        j = min(i + 1, len(self.times) - 1)
        glat, glon = np.meshgrid(domain.grid_lats(), domain.grid_lons(), indexing="ij")
        out = ((1 - w) * bilinear(self.blh[i], self.lats, self.lons, glat, glon)
               + w * bilinear(self.blh[j], self.lats, self.lons, glat, glon))
        out = np.where(np.isnan(out), blh_fallback(t), out)
        return out.astype(np.float32)

    def mean_speed(self, t: datetime) -> float:
        i, _ = self._tindex(t)
        return float(np.mean(np.hypot(self.u[i], self.v[i])))


def background_grid(aq_json: dict, t: datetime) -> np.ndarray:
    """CAMS PM2.5 background on the output grid at time t (bilinear + linear in time)."""
    lats = np.asarray(aq_json["lats"], dtype=np.float64)
    lons = np.asarray(aq_json["lons"], dtype=np.float64)
    times = _parse_times(aq_json["times"])
    pm = _to_array(aq_json["pm25"])
    step = (times[1] - times[0]).total_seconds()
    f = min(max((ensure_utc(t) - times[0]).total_seconds() / step, 0.0), len(times) - 1 - 1e-9)
    i = int(math.floor(f))
    w = f - i
    j = min(i + 1, len(times) - 1)
    glat, glon = np.meshgrid(domain.grid_lats(), domain.grid_lons(), indexing="ij")
    out = (1 - w) * bilinear(pm[i], lats, lons, glat, glon) + w * bilinear(pm[j], lats, lons, glat, glon)
    return np.nan_to_num(out).astype(np.float32)


def _aq_arrays(aq_json: dict):
    lats = np.asarray(aq_json["lats"], dtype=np.float64)
    lons = np.asarray(aq_json["lons"], dtype=np.float64)
    times = _parse_times(aq_json["times"])
    pm = _to_array(aq_json["pm25"])
    step = (times[1] - times[0]).total_seconds()
    return lats, lons, times, pm, step


def _aq_slice(pm: np.ndarray, times: list[datetime], step: float, t: datetime) -> np.ndarray:
    f = min(max((ensure_utc(t) - times[0]).total_seconds() / step, 0.0), len(times) - 1 - 1e-9)
    i = int(math.floor(f))
    w = f - i
    j = min(i + 1, len(times) - 1)
    return np.nan_to_num((1 - w) * pm[i] + w * pm[j])


def background_grid_series(aq_json: dict, hours: list[datetime]) -> dict:
    """CAMS PM2.5 on the coarse wind grid at each output hour: runs/{runId}/background.json.
    Kept coarse (12 x 13) so the file is small; the web app interpolates bilinearly."""
    lats, lons, times, pm, step = _aq_arrays(aq_json)
    series = [np.round(_aq_slice(pm, times, step, t), 1).tolist() for t in hours]
    from common.timeutil import iso_z

    return {"lats": lats.tolist(), "lons": lons.tolist(), "hours": [iso_z(h) for h in hours],
            "units": "ug/m3", "source": aq_json.get("source", "CAMS via open-meteo"), "pm25": series}


def background_points(aq_json: dict, qlat, qlon, hours: list[datetime]) -> np.ndarray:
    """(H, N) CAMS PM2.5 at N points for H hours, bilinear in space, linear in time."""
    lats, lons, times, pm, step = _aq_arrays(aq_json)
    qlat = np.asarray(qlat, dtype=np.float64)
    qlon = np.asarray(qlon, dtype=np.float64)
    out = np.zeros((len(hours), qlat.shape[0]), dtype=np.float32)
    for h, t in enumerate(hours):
        out[h] = bilinear(_aq_slice(pm, times, step, t), lats, lons, qlat, qlon)
    return out


def wind_series(wind_json: dict, hours: list[datetime]) -> dict:
    """Blended (925 hPa / 10 m) u, v on the 0.5 deg grid per output hour: runs/{runId}/wind.json,
    ~100 KB, for the arrow layer (DESIGN.md §9.2 layer 2)."""
    from common.timeutil import iso_z

    w = WindField(wind_json)
    u, v = [], []
    for t in hours:
        i, frac = w._tindex(t)
        j = min(i + 1, len(w.times) - 1)
        u.append(np.round(((1 - frac) * w.u[i] + frac * w.u[j]).astype(np.float64), 1).tolist())
        v.append(np.round(((1 - frac) * w.v[i] + frac * w.v[j]).astype(np.float64), 1).tolist())
    return {"lats": w.lats.tolist(), "lons": w.lons.tolist(), "hours": [iso_z(h) for h in hours], "units": "m/s",
            "source": w.source, "u": u, "v": v}


def precip_sum(wind_json: dict, t_from: datetime, t_to: datetime) -> np.ndarray:
    """Total precipitation (mm) on the coarse grid between two times; zeros when absent."""
    lats = np.asarray(wind_json["lats"])
    lons = np.asarray(wind_json["lons"])
    if not wind_json.get("precip"):
        return np.zeros((len(lats), len(lons)), dtype=np.float32)
    times = _parse_times(wind_json["times"])
    arr = np.nan_to_num(_to_array(wind_json["precip"], fill_forward=False))
    idx = [i for i, t in enumerate(times) if ensure_utc(t_from) <= t < ensure_utc(t_to)]
    return arr[idx].sum(axis=0).astype(np.float32) if idx else np.zeros((len(lats), len(lons)), dtype=np.float32)
