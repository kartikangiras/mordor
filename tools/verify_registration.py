#!/usr/bin/env python3
"""Gate 1 / R5 check without a browser: composite a run's overlay onto satellite tiles the way
MapLibre does (Web Mercator, corners = domain), draw the fires, and save a PNG to look at.

    PYTHONPATH=services python tools/verify_registration.py --run web/public/dev/runs/<runId> --hour 1 --out /tmp/check.png
"""
from __future__ import annotations

import argparse
import io
import json
import math
import sys
from pathlib import Path

import requests
from PIL import Image, ImageDraw

from common import domain

TILE = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
CITIES = {"Delhi": (28.6139, 77.2090), "Ludhiana": (30.9010, 75.8573), "Chandigarh": (30.7333, 76.7794),
          "Amritsar": (31.634, 74.872), "Jaipur": (26.9124, 75.7873), "Bathinda": (30.21, 74.95)}


def merc_px(lat: float, lon: float, z: int) -> tuple[float, float]:
    n = 256 * 2 ** z
    x = (lon + 180) / 360 * n
    y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--hour", type=int, default=0)
    ap.add_argument("--zoom", type=int, default=7)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    run = Path(a.run)
    z = a.zoom
    w, s, e, n = domain.DOMAIN_WSEN
    pad = 0.6
    x0, y0 = merc_px(n + pad, w - pad, z)
    x1, y1 = merc_px(s - pad, e + pad, z)
    tx0, ty0, tx1, ty1 = int(x0 // 256), int(y0 // 256), int(x1 // 256), int(y1 // 256)
    canvas = Image.new("RGBA", ((tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256), (0, 0, 0, 255))
    sess = requests.Session()
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            r = sess.get(TILE.format(z=z, x=tx, y=ty), timeout=30)
            if r.ok:
                canvas.paste(Image.open(io.BytesIO(r.content)).convert("RGBA"), ((tx - tx0) * 256, (ty - ty0) * 256))
    ox, oy = tx0 * 256, ty0 * 256

    def px(lat, lon):
        x, y = merc_px(lat, lon, z)
        return x - ox, y - oy

    # overlay: MapLibre maps the four corners; for an axis-aligned lat/lon box that is a Mercator rectangle
    left, top = px(n, w)
    right, bottom = px(s, e)
    overlay = Image.open(run / "overlay" / f"{a.hour:02d}.png").convert("RGBA")
    overlay = overlay.resize((int(right - left), int(bottom - top)), Image.BILINEAR)
    canvas.alpha_composite(overlay, (int(left), int(top)))
    d = ImageDraw.Draw(canvas)
    d.rectangle([left, top, right, bottom], outline=(255, 255, 255, 180), width=1)
    fires = json.loads((run / "fires.geojson").read_text())
    for f in fires["features"]:
        lon, lat = f["geometry"]["coordinates"]
        x, y = px(lat, lon)
        rr = 2 + min(4, f["properties"].get("frp", 1) / 8)
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(255, 179, 71, 220), outline=(124, 43, 63, 255))
    for name, (lat, lon) in CITIES.items():
        x, y = px(lat, lon)
        d.ellipse([x - 4, y - 4, x + 4, y + 4], outline=(0, 255, 255, 255), width=2)
        d.text((x + 6, y - 6), name, fill=(0, 255, 255, 255))
    manifest = json.loads((run / "manifest.json").read_text())
    d.text((8, 8), f"{manifest['runId']} hour +{a.hour} {manifest['hours'][a.hour]}  cyan=city (truth)  magenta=overlay marker  orange=VIIRS fire", fill=(255, 255, 255, 255))
    canvas.convert("RGB").save(a.out)
    print("wrote", a.out, canvas.size, "fires", len(fires["features"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
