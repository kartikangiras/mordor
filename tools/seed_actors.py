#!/usr/bin/env python3
"""Onboard entities of any actor type (DESIGN.md §6.6, §7.1): schools, RWAs, district
agriculture offices. Contacts go to DynamoDB only; the public fields go to static/actors.json
(and schools are merged into static/schools.geojson so the map knows them).

    PYTHONPATH=services python tools/seed_actors.py            # demo entities + data/actors.json if present

Entry fields: id, type (school|rwa|agri_officer), name, name_hi, lat, lon, hours, dismissal,
hasPurifiers, students|residents|machines, district + radiusKm (agri_officer), principal/contact,
phone (E.164, WhatsApp), email, demo (bool). Phone numbers never leave DynamoDB.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from common import ddb
from common.storage import LocalStorage, storage
from common.timeutil import iso_z, utc_now
from protocol.actors import ACTOR_TYPES
from records import store as records

PUBLIC = ("id", "type", "name", "name_hi", "lat", "lon", "hours", "dismissal", "hasPurifiers", "students", "residents",
          "machines", "beds", "district", "radiusKm", "demo", "persona")
PRIVATE = ("contact", "principal", "phone", "email", "principalSub")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", default="data/actors.demo.json")
    ap.add_argument("--file", default="data/actors.json")
    ap.add_argument("--schools", default="data/schools.geojson")
    ap.add_argument("--records-store", default=None, help="write EntityRegistration records here (default: the main store)")
    ap.add_argument("--no-records", action="store_true")
    a = ap.parse_args()
    entries = json.loads(Path(a.demo).read_text()) if Path(a.demo).exists() else []
    if Path(a.file).exists():
        entries += json.loads(Path(a.file).read_text())
    bad = [e.get("id") for e in entries if e.get("type") not in ACTOR_TYPES or not all(k in e for k in ("id", "name", "lat", "lon"))]
    if bad:
        print(f"bad entries (unknown type or missing id/name/lat/lon): {bad}", file=sys.stderr)
        return 2
    # A school's point is the school's point: take it from schools.geojson when the id is there, so a
    # hand-typed seed can never sit 1.2 km from the dot the map draws (PIVOT_PLAN.md P4).
    gj = json.loads(Path(a.schools).read_text())
    by_id = {f["properties"]["id"]: f for f in gj["features"]}
    for e in entries:
        if e["type"] == "school" and e["id"] in by_id:
            lon, lat = by_id[e["id"]]["geometry"]["coordinates"]
            if (round(lat, 5), round(lon, 5)) != (round(e["lat"], 5), round(e["lon"], 5)):
                print(f"{e['id']}: point taken from schools.geojson ({lat}, {lon}) instead of the seed ({e['lat']}, {e['lon']})")
            e["lat"], e["lon"] = lat, lon
    now = iso_z(utc_now())
    items = []
    for e in entries:
        items.append({"PK": f"SCHOOL#{e['id']}", "SK": "META", **{k: e.get(k) for k in PUBLIC if k in e},
                      **{k: e.get(k) for k in PRIVATE if k in e}, "source": "onboarded", "onboardedAt": e.get("onboardedAt", now)})
    written = ddb.put_items(items)
    if not a.no_records:
        lstore = LocalStorage(a.records_store) if a.records_store else storage()
        n_led = 0
        for e in entries:
            if any(r["kind"] == "enrol" for r in records.records_for(e["id"], lstore)):
                continue
            records.append("enrol", e["id"], {"type": e["type"], "name": e["name"], "lat": e["lat"], "lon": e["lon"],
                                              "hours": e.get("hours"), "dismissal": e.get("dismissal"), "district": e.get("district"),
                                              "people": e.get("students") or e.get("residents") or e.get("machines") or e.get("beds"), "demo": bool(e.get("demo")),
                                              "persona": e.get("persona"), "verifiedBy": "registry" if e.get("demo") else "pending verifier approval"},
                          e["type"], by={"role": "operator", "persona": e.get("persona")}, store=lstore)
            n_led += 1
        print(f"{n_led} EntityRegistration records written")
    public = [{k: e.get(k) for k in PUBLIC if k in e} | {"onboarded": not e.get("demo", False)} for e in entries]
    storage().put_json("static/actors.json", {"generatedAt": now, "entities": public})
    Path("data/actors.public.json").write_text(json.dumps({"generatedAt": now, "entities": public}, ensure_ascii=False, indent=1))
    for e in entries:
        if e["type"] != "school":
            continue
        props = {"id": e["id"], "name": e["name"], "name_hi": e.get("name_hi"), "named": True, "students": e.get("students"),
                 "demo": bool(e.get("demo")), "onboarded": not e.get("demo", False)}
        if e["id"] in by_id:
            by_id[e["id"]]["properties"].update(props)
        else:
            gj["features"].append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [e["lon"], e["lat"]]}, "properties": props})
    Path(a.schools).write_text(json.dumps(gj, ensure_ascii=False, separators=(",", ":")))
    storage().put_json("static/schools.geojson", gj)
    print(f"{len(entries)} entities ({', '.join(sorted({e['type'] for e in entries}))}): {written} DynamoDB META items "
          f"({'DynamoDB disabled' if not ddb.enabled() else 'ok'}); static/actors.json + static/schools.geojson updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
