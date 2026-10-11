"""Bake web/src/config/streets.json: the road, boundary and label layers of OpenFreeMap's
`liberty` style (OpenMapTiles schema, OpenStreetMap data, ODbL), restyled to sit on satellite
imagery: translucent light roads with a dark casing, white labels with a dark halo. Keyless.

    python tools/bake_streets.py            # fetches https://tiles.openfreemap.org/styles/liberty
"""
from __future__ import annotations

import json
import pathlib
import sys
import urllib.request

STYLE_URL = "https://tiles.openfreemap.org/styles/liberty"
OUT = pathlib.Path(__file__).resolve().parents[1] / "web" / "src" / "config" / "streets.json"
KEEP = ["boundary_3", "boundary_2", "boundary_disputed", "aeroway_runway", "aeroway_taxiway",
        "road_motorway_casing", "road_trunk_primary_casing", "road_secondary_tertiary_casing", "road_minor_casing",
        "road_motorway", "road_trunk_primary", "road_secondary_tertiary", "road_minor", "road_major_rail", "road_major_rail_hatching",
        "bridge_motorway_casing", "bridge_trunk_primary_casing", "bridge_secondary_tertiary_casing",
        "bridge_motorway", "bridge_trunk_primary", "bridge_secondary_tertiary", "bridge_major_rail",
        "waterway_line_label", "water_name_point_label", "water_name_line_label",
        "poi_r20", "poi_r7", "poi_r1", "poi_transit",
        "highway-name-minor", "highway-name-major", "highway-shield-non-us", "airport",
        "label_other", "label_village", "label_town", "label_state", "label_city", "label_city_capital",
        "label_country_3", "label_country_2", "label_country_1"]


def line_colour(lid: str) -> str:
    if "casing" in lid:
        return "rgba(0,0,0,0.3)"
    if "motorway" in lid:
        return "rgba(242,197,114,0.8)"
    if "trunk_primary" in lid:
        return "rgba(255,255,255,0.62)"
    if "secondary_tertiary" in lid:
        return "rgba(255,255,255,0.45)"
    if "minor" in lid:
        return "rgba(255,255,255,0.3)"
    if "rail" in lid:
        return "rgba(0,0,0,0.5)" if "hatching" in lid else "rgba(255,255,255,0.45)"
    if lid == "boundary_2":
        return "rgba(255,255,255,0.8)"
    if lid == "boundary_3":
        return "rgba(255,255,255,0.45)"
    return "rgba(255,255,255,0.6)"


def bake(style: dict) -> list[dict]:
    by = {lg["id"]: lg for lg in style["layers"]}
    out = []
    for lid in KEEP:
        layer = json.loads(json.dumps(by[lid]))
        layer["id"] = f"streets-{lid}"
        if "shield" in lid:   # refs without a length made MapLibre warn "expected number, found null"
            layer["filter"] = json.loads(json.dumps(layer["filter"]).replace('["get", "ref_length"]', '["coalesce", ["get", "ref_length"], 99]'))
        paint = layer.setdefault("paint", {})
        if layer["type"] == "line":
            paint["line-color"] = line_colour(lid)
            paint.pop("line-opacity", None)
            if lid in ("road_minor", "road_minor_casing"):
                layer["minzoom"] = 12
            if lid in ("road_secondary_tertiary", "road_secondary_tertiary_casing"):
                layer["minzoom"] = max(layer.get("minzoom", 0), 9)
        elif layer["type"] == "symbol":
            paint["text-color"] = "rgba(255,255,255,0.72)" if ("state" in lid or "country" in lid) else "#ffffff"
            paint["text-halo-color"] = "rgba(8,10,14,0.85)"
            paint["text-halo-width"] = 1.4
            paint["text-halo-blur"] = 0.4
            if lid.startswith("poi"):
                paint["icon-opacity"] = 0.9
            if lid == "label_other":
                layer["minzoom"] = 11
            if lid == "label_village":
                layer["minzoom"] = 10
            # one script per label: English or Latin name only; the product's own Hindi lives in the cards
            if "name" in json.dumps(layer.get("layout", {}).get("text-field", "")):   # not the shields, which show `ref`
                layer["layout"]["text-field"] = ["coalesce", ["get", "name:en"], ["get", "name:latin"], ["get", "name"]]
        out.append(layer)
    return out


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--from":      # a saved copy of the style JSON
        with open(sys.argv[2]) as fh:
            style = json.load(fh)
    else:
        req = urllib.request.Request(STYLE_URL, headers={"User-Agent": "mordor/bake_streets (+https://github.com)"})
        with urllib.request.urlopen(req, timeout=30) as r:
            style = json.load(r)
    layers = bake(style)
    OUT.write_text(json.dumps({"note": "Road, boundary and label layers from OpenFreeMap's liberty style (OpenMapTiles schema, ODbL OpenStreetMap data), restyled for a satellite ground: light lines, white text with a dark halo. Regenerate with tools/bake_streets.py.", "layers": layers}, separators=(",", ":")))
    print(f"{len(layers)} layers -> {OUT}")
    sys.exit(0)
