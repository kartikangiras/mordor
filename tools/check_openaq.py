#!/usr/bin/env python3
"""Resolve DESIGN.md §4.4 in one run: does OpenAQ v3 hold hourly PM2.5 history for Delhi CPCB
stations over the hindcast window (1-20 Nov 2025)?

    OPENAQ_API_KEY=... python tools/check_openaq.py

Prints station count, a sample of hourly rows, and a verdict:
  PRIMARY   -> quantitative hindcast (§13.1) is on
  FALLBACK  -> use the qualitative hindcast (§13.3)
"""
from __future__ import annotations

import os
import sys

import requests

API = "https://api.openaq.org/v3"
DELHI = (28.61, 77.21)
WINDOW = ("2025-11-01T00:00:00Z", "2025-11-03T00:00:00Z")
PM25_PARAMETER_ID = 2


def main() -> int:
    key = os.environ.get("OPENAQ_API_KEY")
    if not key:
        print("OPENAQ_API_KEY not set", file=sys.stderr)
        return 2
    s = requests.Session()
    s.headers["X-API-Key"] = key
    r = s.get(f"{API}/locations", params={"coordinates": f"{DELHI[0]},{DELHI[1]}", "radius": 25000,
                                          "parameters_id": PM25_PARAMETER_ID, "limit": 200}, timeout=60)
    r.raise_for_status()
    locs = r.json().get("results", [])
    print(f"locations within 25 km of Delhi with PM2.5: {len(locs)}")
    with_history = 0
    for loc in locs[:40]:
        sensors = [x for x in loc.get("sensors", []) if x.get("parameter", {}).get("id") == PM25_PARAMETER_ID]
        if not sensors:
            continue
        sid = sensors[0]["id"]
        h = s.get(f"{API}/sensors/{sid}/hours", params={"datetime_from": WINDOW[0], "datetime_to": WINDOW[1],
                                                        "limit": 100}, timeout=60)
        if h.status_code != 200:
            print(f"  {loc.get('name')!r}: HTTP {h.status_code}")
            continue
        rows = h.json().get("results", [])
        if rows:
            with_history += 1
            v = rows[0]
            print(f"  {loc.get('name')!r} sensor {sid}: {len(rows)} hourly rows, first {v.get('period', {}).get('datetimeFrom', {}).get('utc')} = {v.get('value')}")
        else:
            print(f"  {loc.get('name')!r} sensor {sid}: no rows in window")
    print()
    if with_history >= 10:
        print(f"VERDICT: PRIMARY - {with_history} stations with hourly history. Quantitative hindcast is on.")
        return 0
    print(f"VERDICT: FALLBACK - only {with_history} stations with history. Use the qualitative hindcast (§13.3).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
