"""Vegetation change from NASA GIBS NDVI 8-day composites (VIIRS NOAA-20), keyless.

GIBS serves paletted PNG tiles whose palette is documented by a colormap XML; mapping palette
colours back to NDVI values gives a numeric field. We compare the latest composite with the
one two periods earlier (16 days) on the 0.25 deg burning grid: a drop means harvest or burn,
which is the "fuel is ready" signal in the burning-risk score. Cloud/no-data is NaN.
"""
from __future__ import annotations

import io
import logging
import math
import re
from datetime import date, datetime, timedelta

import numpy as np
import requests
from PIL import Image

from common import domain
from common.storage import Storage

log = logging.getLogger(__name__)

LAYER = "VIIRS_NOAA20_NDVI_8Day"
MATRIX = "GoogleMapsCompatible_Level8"
ZOOM = 7
TILE = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/{layer}/default/{date}/{matrix}/{z}/{y}/{x}.png"
COLORMAP = "https://gibs.earthdata.nasa.gov/colormaps/v1.3/MODIS_NDVI.xml"  # shared NDVI palette (legend MODIS_NDVI_H)
CAPS = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/1.0.0/WMTSCapabilities.xml"
TIMEOUT = 40


def latest_composite_date(session: requests.Session | None = None) -> date | None:
    """The layer's default (latest) date from the WMTS capabilities."""
    try:
        x = (session or requests).get(CAPS, timeout=TIMEOUT).text
        m = re.search(r"<ows:Identifier>" + LAYER + r"</ows:Identifier>(?:(?!</Layer>).)*?<Default>(\d{4}-\d{2}-\d{2})</Default>", x, re.S)
        return date.fromisoformat(m.group(1)) if m else None
    except requests.RequestException as exc:
        log.warning("GIBS capabilities unavailable: %s", exc)
        return None


def parse_colormap(xml: str) -> dict[tuple[int, int, int], float]:
    """rgb -> NDVI midpoint, from ColorMapEntry rgb="r,g,b" value="[a,b)" (or sourceValue)."""
    out: dict[tuple[int, int, int], float] = {}
    for m in re.finditer(r"<ColorMapEntry([^>]*)/?>", xml):
        attrs = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
        if attrs.get("transparent", "false").lower() == "true":
            continue
        rgb = tuple(int(v) for v in attrs.get("rgb", "").split(",")) if attrs.get("rgb") else None
        val = attrs.get("value") or attrs.get("sourceValue")
        if not rgb or len(rgb) != 3 or not val:
            continue
        nums = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?(?:e-?\d+)?", val)]
        if not nums:
            continue
        v = round(sum(nums[:2]) / len(nums[:2]), 4)
        if -1.0 <= v <= 1.0:
            out[rgb] = v
    return out


def _tile_xy(lat: float, lon: float, z: int) -> tuple[int, int]:
    n = 2 ** z
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


def _pixel_latlon(x: int, y: int, z: int, size: int = 256) -> tuple[np.ndarray, np.ndarray]:
    n = 2 ** z
    px = (np.arange(size) + 0.5) / size
    lons = (x + px) / n * 360 - 180
    ys = (y + px) / n
    lats = np.degrees(np.arctan(np.sinh(np.pi * (1 - 2 * ys))))
    return lats, lons


def fetch_field(day: date, cmap: dict, store: Storage | None = None, session: requests.Session | None = None,
                cell: float = 0.25) -> np.ndarray:
    """Mean NDVI per `cell`-degree cell over the domain for one composite date; NaN where unseen."""
    sess = session or requests.Session()
    nlat, nlon = int(round((domain.LAT_MAX - domain.LAT_MIN) / cell)), int(round((domain.LON_MAX - domain.LON_MIN) / cell))
    acc = np.zeros((nlat, nlon))
    cnt = np.zeros((nlat, nlon))
    x0, y0 = _tile_xy(domain.LAT_MAX, domain.LON_MIN, ZOOM)
    x1, y1 = _tile_xy(domain.LAT_MIN, domain.LON_MAX, ZOOM)
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            key = f"raw/gibs/{LAYER}/{day:%Y-%m-%d}/{ZOOM}_{x}_{y}.png"
            raw = store.get(key) if store else None
            if raw is None:
                r = sess.get(TILE.format(layer=LAYER, date=day.isoformat(), matrix=MATRIX, z=ZOOM, y=y, x=x), timeout=TIMEOUT)
                if r.status_code != 200:
                    continue
                raw = r.content
                if store:
                    store.put(key, raw, "image/png")
            im = Image.open(io.BytesIO(raw)).convert("RGB")
            arr = np.asarray(im)
            lut = np.full(arr.shape[:2], np.nan)
            # map each distinct colour once
            flat = arr.reshape(-1, 3)
            uniq, inv = np.unique(flat, axis=0, return_inverse=True)
            vals = np.array([cmap.get(tuple(int(c) for c in u), np.nan) for u in uniq])
            lut = vals[inv].reshape(arr.shape[:2])
            lats, lons = _pixel_latlon(x, y, ZOOM)
            glat, glon = np.meshgrid(lats, lons, indexing="ij")
            ok = ~np.isnan(lut) & domain.in_domain(glat, glon)
            i = np.floor((glat[ok] - domain.LAT_MIN) / cell).astype(int)
            j = np.floor((glon[ok] - domain.LON_MIN) / cell).astype(int)
            np.add.at(acc, (i, j), lut[ok])
            np.add.at(cnt, (i, j), 1)
    with np.errstate(invalid="ignore"):
        return np.where(cnt > 0, acc / np.maximum(cnt, 1), np.nan)


def ndvi_change(now: datetime, store: Storage | None = None, session: requests.Session | None = None) -> dict | None:
    """{date, prevDate, now: grid, prev: grid, change: grid} on the 0.25 deg grid, or None."""
    sess = session or requests.Session()
    latest = latest_composite_date(sess)
    if latest is None:
        return None
    try:
        cmap = parse_colormap(sess.get(COLORMAP.format(layer=LAYER), timeout=TIMEOUT).text)
    except requests.RequestException as exc:
        log.warning("GIBS colormap unavailable: %s", exc)
        return None
    if len(cmap) < 10:
        log.warning("GIBS colormap parsed only %d entries", len(cmap))
        return None
    prev = latest - timedelta(days=16)
    cur_f = fetch_field(latest, cmap, store, sess)
    prev_f = fetch_field(prev, cmap, store, sess)
    return {"layer": LAYER, "date": latest.isoformat(), "prevDate": prev.isoformat(), "zoom": ZOOM,
            "tileTemplate": TILE.format(layer=LAYER, date=latest.isoformat(), matrix=MATRIX, z="{z}", y="{y}", x="{x}"),
            "now": cur_f, "prev": prev_f, "change": cur_f - prev_f, "colormapEntries": len(cmap)}
