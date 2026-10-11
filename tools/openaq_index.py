#!/usr/bin/env python3
"""Build data/openaq_stations.json from the keyless OpenAQ open-data archive on S3
(registry.opendata.aws/openaq): every location id in the domain with hourly PM2.5 during the
given month(s). Run once; the output is committed. No API key needed.

    PYTHONPATH=services python tools/openaq_index.py --months 2025-11 2024-11 --max-id 12000
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

from common import domain

BUCKET = "https://openaq-data-archive.s3.amazonaws.com"
KEY_RE = re.compile(r"<Key>([^<]+)</Key>")


def month_keys(sess: requests.Session, loc: int, ym: str) -> list[str]:
    y, m = ym.split("-")
    prefix = f"records/csv.gz/locationid={loc}/year={y}/month={m}/"
    for attempt in range(3):
        try:
            r = sess.get(f"{BUCKET}/?list-type=2&prefix={prefix}&max-keys=40", timeout=30)
            if r.status_code == 200:
                return KEY_RE.findall(r.text)
        except requests.RequestException:
            time.sleep(1 + attempt)
    return []


def describe(sess: requests.Session, key: str) -> dict | None:
    r = sess.get(f"{BUCKET}/{key}", timeout=60)
    if r.status_code != 200:
        return None
    rows = list(csv.DictReader(io.StringIO(gzip.decompress(r.content).decode())))
    pm = [x for x in rows if x["parameter"] == "pm25"]
    if not pm:
        return None
    x = pm[0]
    return {"id": int(x["location_id"]), "sensorId": int(x["sensors_id"]), "name": x["location"],
            "lat": float(x["lat"]), "lon": float(x["lon"]), "units": x["units"]}


def probe(sess: requests.Session, loc: int, months: list[str]) -> dict | None:
    found = {}
    for ym in months:
        keys = month_keys(sess, loc, ym)
        if keys:
            found[ym] = len(keys)
    if not found:
        return None
    first_month = next(iter(found))
    keys = month_keys(sess, loc, first_month)
    d = describe(sess, keys[0])
    if not d or not bool(domain.in_domain(d["lat"], d["lon"])):
        return None
    d["daysByMonth"] = found
    return d


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", nargs="+", default=["2025-11", "2024-11"])
    ap.add_argument("--min-id", type=int, default=1)
    ap.add_argument("--max-id", type=int, default=12000)
    ap.add_argument("--workers", type=int, default=32)
    ap.add_argument("--out", default="data/openaq_stations.json")
    a = ap.parse_args()
    sess = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=a.workers, pool_maxsize=a.workers)
    sess.mount("https://", adapter)
    hits: list[dict] = []
    started = time.time()
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(probe, sess, i, a.months): i for i in range(a.min_id, a.max_id + 1)}
        for done, f in enumerate(as_completed(futs), 1):
            d = f.result()
            if d:
                hits.append(d)
                print(f"hit {d['id']:6d} {d['name'][:40]:40s} {d['lat']:.3f},{d['lon']:.3f} {d['daysByMonth']}", flush=True)
            if done % 1000 == 0:
                print(f"... {done} ids probed, {len(hits)} hits, {time.time() - started:.0f}s", flush=True)
    hits.sort(key=lambda d: d["id"])
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps({"source": "openaq-data-archive (AWS Open Data), keyless",
                                       "months": a.months, "idRange": [a.min_id, a.max_id],
                                       "stations": hits}, indent=1))
    print(f"wrote {a.out}: {len(hits)} in-domain stations with PM2.5 in {a.months} ({time.time() - started:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
