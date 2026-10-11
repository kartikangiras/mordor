#!/usr/bin/env python3
"""Load onboarded schools (the Day-2 fieldwork) into DynamoDB as SCHOOL#{id}/META
(DESIGN.md §7.1) and merge them into static/schools.geojson so the map knows them.

    cp data/onboarded.example.json data/onboarded.json   # fill in real schools (git-ignored)
    PYTHONPATH=services python tools/seed_schools.py --file data/onboarded.json

Each entry: id (an OSM id from data/schools.geojson, or "school-<slug>"), name, name_hi, lat,
lon, principal, phone (WhatsApp, E.164), email, hours ["08:00","14:00"], dismissal
["15:00","16:00"], hasPurifiers, students. Phone numbers never leave DynamoDB.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from common import ddb
from common.storage import storage
from common.timeutil import iso_z, utc_now

REQUIRED = ("id", "name", "lat", "lon", "principal", "phone")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="data/onboarded.json")
    ap.add_argument("--schools", default="data/schools.geojson")
    a = ap.parse_args()
    entries = json.loads(Path(a.file).read_text())
    bad = [e.get("id") for e in entries if any(k not in e for k in REQUIRED)]
    if bad:
        print(f"entries missing one of {REQUIRED}: {bad}", file=sys.stderr)
        return 2
    now = iso_z(utc_now())
    items = [{"PK": f"SCHOOL#{e['id']}", "SK": "META", "name": e["name"], "name_hi": e.get("name_hi"),
              "lat": e["lat"], "lon": e["lon"], "hours": e.get("hours", ["08:00", "14:00"]),
              "dismissal": e.get("dismissal", ["15:00", "16:00"]), "hasPurifiers": bool(e.get("hasPurifiers")),
              "principal": e["principal"], "phone": e["phone"], "email": e.get("email"),
              "students": e.get("students"), "principalSub": e.get("principalSub"),
              "source": "onboarded", "onboardedAt": e.get("onboardedAt", now)} for e in entries]
    written = ddb.put_items(items)
    # merge into the schools layer (public fields only)
    gj = json.loads(Path(a.schools).read_text())
    by_id = {f["properties"]["id"]: f for f in gj["features"]}
    for e in entries:
        f = by_id.get(e["id"])
        props = {"id": e["id"], "name": e["name"], "name_hi": e.get("name_hi"), "named": True, "onboarded": True,
                 "students": e.get("students"), "source": "onboarded"}
        if f:
            f["properties"].update(props)
        else:
            gj["features"].append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [e["lon"], e["lat"]]},
                                   "properties": props})
    Path(a.schools).write_text(json.dumps(gj, ensure_ascii=False, separators=(",", ":")))
    storage().put_json("static/schools.geojson", gj)
    print(f"{len(entries)} schools: {written} DynamoDB META items written "
          f"({'DynamoDB disabled' if not ddb.enabled() else 'ok'}); static/schools.geojson updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
