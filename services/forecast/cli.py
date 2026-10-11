"""Local forecast driver (DESIGN.md §10.5): runs the same five steps as the Step Functions
state machine, reading inputs from LOCAL_DATA_DIR (./.data) and writing the run into a
directory the Vite dev server serves at /dev.

    make forecast-local                      # 48 h from cached inputs -> web/public/dev
    make forecast-local HOURS=1              # single hour (M3 gate)
    PYTHONPATH=services python -m forecast.cli --fetch --debug-markers
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime

from common import domain
from common.storage import LocalStorage, storage
from common.timeutil import utc_now
from forecast import steps
from forecast.run import Params
from ingest_firms import firms
from ingest_weather import openmeteo


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="mordor local forecast run")
    ap.add_argument("--hours", type=int, default=domain.FORECAST_HOURS)
    ap.add_argument("--out", default="web/public/dev", help="output directory (served by vite at /dev)")
    ap.add_argument("--now", default=None, help="ISO UTC time to run for (default: now)")
    ap.add_argument("--fetch", action="store_true", help="run the FIRMS + weather ingests first")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--debug-markers", action="store_true", help="stamp registration crosses at Delhi/Ludhiana/Chandigarh")
    ap.add_argument("--no-latest", action="store_true", help="do not move runs/latest.json")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    now = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else utc_now()
    if args.fetch:
        firms.run(now=now)
        openmeteo.run(now=now)
    if not firms.load_recent(24, now=now):
        print("no fires in the last 24 h in storage; run with --fetch or `make ingest-firms`", file=sys.stderr)
        return 2
    params = Params()
    if args.seed is not None:
        params.seed = args.seed
    out = LocalStorage(args.out)
    # the dev API (LOCAL_DATA_DIR=web/public/dev) needs the static layer next to the runs
    for name in ("static/schools.geojson", "static/climatology_2024.json", "static/actors.json"):
        blob = storage().get(name)
        if blob:
            out.put(name, blob, "application/json")
    ctx = steps.run_all(storage(), out, now=now, hours=args.hours, params=params,
                        debug_markers=args.debug_markers, write_latest=not args.no_latest)
    print(json.dumps({k: ctx[k] for k in ("runId", "hours", "fires", "weather", "overlay", "k", "schools", "stats")
                      if k in ctx}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
