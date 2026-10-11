#!/usr/bin/env python3
"""Overpass, run once (DESIGN.md §4.5): schools in Delhi as data/schools.geojson. Overpass is
rate-limited and flaky, so this is never called at runtime; the output is committed and
uploaded to S3 as static/schools.geojson.

    PYTHONPATH=services python tools/fetch_schools.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import requests

BBOX = (28.40, 76.83, 28.89, 77.35)  # S, W, N, E  (Delhi NCT + a margin)
ENDPOINTS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
             "https://overpass.private.coffee/api/interpreter"]
QUERY = """[out:json][timeout:180];
(
  node["amenity"="school"]({s},{w},{n},{e});
  way["amenity"="school"]({s},{w},{n},{e});
  relation["amenity"="school"]({s},{w},{n},{e});
);
out center tags;
"""
KEEP_TAGS = ("name", "name:hi", "operator:type", "operator", "isced:level", "school", "addr:city", "addr:postcode")


def fetch() -> dict:
    q = QUERY.format(s=BBOX[0], w=BBOX[1], n=BBOX[2], e=BBOX[3])
    last = None
    for url in ENDPOINTS:
        for attempt in range(2):
            try:
                r = requests.post(url, data={"data": q}, timeout=240, headers={"User-Agent": "mordor/0.1 (hackathon)"})
                if r.status_code == 200:
                    return r.json()
                last = f"{url}: HTTP {r.status_code} {r.text[:120]}"
            except requests.RequestException as exc:
                last = f"{url}: {exc}"
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"all Overpass endpoints failed: {last}")


def _dist_m(a, b) -> float:
    dlat = (a[0] - b[0]) * 111_320
    dlon = (a[1] - b[1]) * 111_320 * math.cos(math.radians(a[0]))
    return math.hypot(dlat, dlon)


def to_geojson(osm: dict) -> dict:
    feats = []
    for el in osm.get("elements", []):
        if el["type"] == "node":
            lat, lon = el.get("lat"), el.get("lon")
        else:
            c = el.get("center") or {}
            lat, lon = c.get("lat"), c.get("lon")
        if lat is None or lon is None:
            continue
        tags = el.get("tags", {})
        name = (tags.get("name") or "").strip() or None
        props = {"id": f"osm-{el['type']}-{el['id']}", "name": name, "name_hi": tags.get("name:hi"),
                 "named": bool(name), "source": "OpenStreetMap"}
        for k in KEEP_TAGS:
            if k in tags and k not in ("name", "name:hi"):
                props[k.replace(":", "_")] = tags[k]
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]},
                      "properties": props})
    # dedupe within 100 m: keep the named one, else the first
    feats.sort(key=lambda f: (not f["properties"]["named"], f["properties"]["id"]))
    kept: list[dict] = []
    cell: dict[tuple, list[dict]] = {}
    for f in feats:
        lon, lat = f["geometry"]["coordinates"]
        key = (round(lat / 0.002), round(lon / 0.002))
        dup = False
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                for g in cell.get((key[0] + dy, key[1] + dx), []):
                    glon, glat = g["geometry"]["coordinates"]
                    if _dist_m((lat, lon), (glat, glon)) < 100 and (
                            f["properties"]["name"] == g["properties"]["name"] or not f["properties"]["named"]):
                        dup = True
                        break
                if dup:
                    break
            if dup:
                break
        if not dup:
            kept.append(f)
            cell.setdefault(key, []).append(f)
    kept.sort(key=lambda f: f["properties"]["id"])
    return {"type": "FeatureCollection", "bbox": [BBOX[1], BBOX[0], BBOX[3], BBOX[2]],
            "source": "OpenStreetMap via Overpass, amenity=school, deduplicated within 100 m",
            "fetchedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "features": kept}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/schools.geojson")
    ap.add_argument("--raw", default=None, help="use a saved Overpass JSON instead of fetching")
    a = ap.parse_args()
    osm = json.loads(Path(a.raw).read_text()) if a.raw else fetch()
    gj = to_geojson(osm)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(gj, ensure_ascii=False, separators=(",", ":")))
    named = sum(1 for f in gj["features"] if f["properties"]["named"])
    print(f"wrote {a.out}: {len(gj['features'])} schools ({named} named, {len(gj['features']) - named} unnamed), "
          f"raw elements {len(osm.get('elements', []))}, sha1 {hashlib.sha1(Path(a.out).read_bytes()).hexdigest()[:8]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
