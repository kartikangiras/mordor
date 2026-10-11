#!/usr/bin/env python3
"""One-off: daily fire counts per 0.25 deg cell for 15 Sep - 15 Dec 2024 from the keyless FIRMS
per-country S-NPP archives -> data/climatology_2024.json (uploaded as static/climatology_2024.json).
The burning-risk score reads the +/-7 day window around today's date from this table.

    PYTHONPATH=services python tools/build_climatology.py
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np

from common import domain
from zones.burning import CELL, NLAT, NLON, cell_of

ARCHIVE = Path(".data/raw/hindcast/firms_archive")
START, END = date(2024, 9, 15), date(2024, 12, 15)


def main() -> int:
    files = sorted(ARCHIVE.glob("viirs-snpp_2024_*.csv"))
    if not files:
        print("no archives in", ARCHIVE, "- run tools/hindcast.py once", file=sys.stderr)
        return 2
    days = [(START + timedelta(days=i)).isoformat() for i in range((END - START).days + 1)]
    idx = {d: n for n, d in enumerate(days)}
    counts = np.zeros((len(days), NLAT, NLON), dtype=np.int32)
    for f in files:
        with open(f) as fh:
            for row in csv.DictReader(fh):
                n = idx.get(row.get("acq_date"))
                if n is None or row.get("confidence", "n") in ("l", "low"):
                    continue
                try:
                    lat, lon = float(row["latitude"]), float(row["longitude"])
                except ValueError:
                    continue
                if bool(domain.in_domain(lat, lon)):
                    i, j = cell_of(lat, lon)
                    counts[n, i, j] += 1
    out = {"source": "FIRMS per-country archives viirs-snpp_2024_{India,Pakistan}.csv, confidence != low",
           "cellDeg": CELL, "nlat": NLAT, "nlon": NLON, "days": days, "counts": counts.tolist()}
    Path("data/climatology_2024.json").write_text(json.dumps(out, separators=(",", ":")))
    print(f"wrote data/climatology_2024.json: {len(days)} days, total detections {int(counts.sum())}, peak day {days[int(counts.sum(axis=(1,2)).argmax())]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
