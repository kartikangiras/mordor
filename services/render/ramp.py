"""Colour ramps and PNG writing for the plume overlay (DESIGN.md §5.8).

The overlay is one PNG per hour placed on the map as a MapLibre `image` source with the four
domain corners. MapLibre stretches the image linearly in *Mercator* space, so rows are resampled
to Mercator spacing here; otherwise the overlay would be up to ~1 km off mid-domain (R5).
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image

from common import domain
from common.aqi import PM25_RAMP

UPSCALE = 6
TRANSPARENT_BELOW_UGM3 = 30.0   # the ramp starts at the top of the 'Good' band


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _merc(lat_deg: np.ndarray) -> np.ndarray:
    return np.log(np.tan(np.pi / 4 + np.radians(lat_deg) / 2))


def _inv_merc(y: np.ndarray) -> np.ndarray:
    return np.degrees(2 * np.arctan(np.exp(y)) - np.pi / 2)


def output_pixel_lats(height: int) -> np.ndarray:
    """Latitude of each output row centre, north to south, spaced uniformly in Mercator y."""
    y_n, y_s = _merc(np.array([domain.LAT_MAX]))[0], _merc(np.array([domain.LAT_MIN]))[0]
    ys = y_n - (np.arange(height) + 0.5) / height * (y_n - y_s)
    return _inv_merc(ys)


def upscale_to_mercator(field: np.ndarray, scale: int = UPSCALE) -> np.ndarray:
    """(NLAT, NLON) south-up cell values -> (NLAT*scale, NLON*scale) north-up, bilinear, rows in
    Mercator spacing. Cell values are treated as samples at cell centres; edges are clamped."""
    nlat, nlon = field.shape
    height, width = nlat * scale, nlon * scale
    lats = output_pixel_lats(height)
    lons = domain.LON_MIN + (np.arange(width) + 0.5) / width * (domain.LON_MAX - domain.LON_MIN)
    fy = np.clip((lats - domain.LAT_MIN) / domain.DLAT - 0.5, 0, nlat - 1 - 1e-9)
    fx = np.clip((lons - domain.LON_MIN) / domain.DLON - 0.5, 0, nlon - 1 - 1e-9)
    iy = np.floor(fy).astype(int)
    ix = np.floor(fx).astype(int)
    wy = (fy - iy)[:, None]
    wx = (fx - ix)[None, :]
    iy1 = np.minimum(iy + 1, nlat - 1)
    ix1 = np.minimum(ix + 1, nlon - 1)
    f = field.astype(np.float64)
    return ((1 - wy) * (1 - wx) * f[np.ix_(iy, ix)] + (1 - wy) * wx * f[np.ix_(iy, ix1)]
            + wy * (1 - wx) * f[np.ix_(iy1, ix)] + wy * wx * f[np.ix_(iy1, ix1)])


BAND_SOLID = 0.7   # fraction of each band drawn in its own colour; the rest blends into the next band


def cpcb_rgba(conc: np.ndarray) -> np.ndarray:
    """ug/m3 -> RGBA keyed to the CPCB PM2.5 bands; transparent below 30.

    At a band's lower threshold the pixel has exactly that band's colour (what the legend says).
    Across the last 30 % of the band it blends towards the next band, so the overlay reads as a
    smooth field instead of stair steps at 5 km cell edges. Opacity rises with the band and fades
    in over the first 6 ug/m3 above the transparent floor."""
    thresholds = [float(t) for t, _ in PM25_RAMP]     # 30, 60, 90, 120, 250
    colours = np.array([hex_to_rgb(c) for _, c in PM25_RAMP], dtype=np.float64)
    alphas = np.array([150, 170, 190, 210, 230], dtype=np.float64)
    c = conc.astype(np.float64)
    # position along the band sequence: i + blend, blend 0 for the solid part, 0..1 across the last 30 %
    pos = np.full(c.shape, float(len(thresholds) - 1))
    for i in range(len(thresholds) - 1):
        lo, hi = thresholds[i], thresholds[i + 1]
        start = lo + BAND_SOLID * (hi - lo)
        m = (c >= lo) & (c < hi)
        pos[m] = i + np.clip((c[m] - start) / (hi - start), 0.0, 1.0)
    i0 = np.clip(np.floor(pos).astype(int), 0, len(thresholds) - 1)
    i1 = np.minimum(i0 + 1, len(thresholds) - 1)
    w = (pos - i0)[..., None]
    rgb = colours[i0] * (1 - w) + colours[i1] * w
    alpha = alphas[i0] * (1 - w[..., 0]) + alphas[i1] * w[..., 0]
    alpha = alpha * np.clip((c - TRANSPARENT_BELOW_UGM3) / 6.0, 0.0, 1.0)   # fade in just above the floor
    rgba = np.zeros(c.shape + (4,), dtype=np.uint8)
    rgba[..., :3] = np.round(rgb).astype(np.uint8)
    rgba[..., 3] = np.round(alpha).astype(np.uint8)
    rgba[c < TRANSPARENT_BELOW_UGM3] = 0
    return rgba


RELATIVE_LOW = hex_to_rgb("#F7E07A")
RELATIVE_HIGH = hex_to_rgb("#7C2B3F")


def relative_rgba(raw: np.ndarray, vmax: float) -> np.ndarray:
    """Uncalibrated field -> a single-hue ramp whose opacity tracks raw / vmax. Used until k is
    fitted; the manifest says 'relative' so the UI never presents these as ug/m3."""
    h, w = raw.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    if vmax <= 0:
        return rgba
    x = np.clip(raw / vmax, 0, 1)
    x = np.sqrt(x)  # lift the faint tail so thin plumes are visible
    x = np.round(x * 24) / 24  # quantise: PNG palette stays small, files stay a few KB
    for c in range(3):
        rgba[..., c] = (RELATIVE_LOW[c] + (RELATIVE_HIGH[c] - RELATIVE_LOW[c]) * x).astype(np.uint8)
    rgba[..., 3] = (x * 220).astype(np.uint8)
    rgba[x < 0.03] = 0
    return rgba


def stamp_markers(rgba: np.ndarray, points: list[tuple[float, float]], size: int = 7) -> None:
    """Registration check: draw a magenta cross at each (lat, lon) in image pixel space."""
    h, w = rgba.shape[:2]
    lats = output_pixel_lats(h)
    for lat, lon in points:
        r = int(np.argmin(np.abs(lats - lat)))
        c = int((lon - domain.LON_MIN) / (domain.LON_MAX - domain.LON_MIN) * w)
        for d in range(-size, size + 1):
            for rr, cc in ((r + d, c), (r, c + d)):
                if 0 <= rr < h and 0 <= cc < w:
                    rgba[rr, cc] = (255, 0, 255, 255)


def render_png(field: np.ndarray, mode: str, vmax: float | None = None,
               markers: list[tuple[float, float]] | None = None) -> bytes:
    """field is (NLAT, NLON) south-up. mode 'cpcb' expects ug/m3; 'relative' expects raw units."""
    up = upscale_to_mercator(field)
    rgba = cpcb_rgba(up) if mode == "cpcb" else relative_rgba(up, vmax or float(up.max()))
    if markers:
        stamp_markers(rgba, markers)
    img = Image.fromarray(rgba, "RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def legend(mode: str) -> dict:
    if mode == "cpcb":
        return {"units": "ug/m3", "kind": "cpcb",
                "stops": [{"from": t, "colour": c} for t, c in PM25_RAMP], "transparentBelow": TRANSPARENT_BELOW_UGM3}
    return {"units": "relative", "kind": "relative", "low": "#F7E07A", "high": "#7C2B3F",
            "note": "Uncalibrated: opacity is relative smoke density for this run only. "
                    "Becomes ug/m3 once k is fitted against CPCB observations (DESIGN.md §5.7)."}
