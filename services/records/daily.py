"""The nightly job (03:00 IST, or `python -m records.daily --date YYYY-MM-DD`): for every
entity-day with a forecast, check the outcome at the nearest station when observations exist
(retrying pending ones for a week), then write the impact statement."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta

from common.storage import Storage, storage
from common.timeutil import IST, utc_now
from records import accounting, verification
from records import store as records

log = logging.getLogger(__name__)


def _entities(store: Storage) -> dict[str, dict]:
    data = store.get_json("static/actors.json") or {"entities": []}
    return {e["id"]: e for e in data["entities"]}


def check_entity_day(meta: dict, card: dict, date: str) -> dict:
    if card.get("kind") == "source":
        return {"outcome": "pending", "reason": "source cards are checked against FIRMS 48 h later (fires in actioned cells)", "station": None}
    st = verification.nearest_station(meta["lat"], meta["lon"])
    if not st:
        return {"outcome": "no_station", "reason": "no indexed station within 25 km", "station": None}
    hours = verification.observed_hours_openaq(st["id"], date)
    if hours is None:
        return {"outcome": "pending", "reason": "observations not published yet (archive lags ~4 days; next-day with the CPCB key)", "station": st}
    windows = [card.get("schoolHoursIst") or ["08:00", "14:00"], card.get("dismissalIst") or ["15:00", "16:00"]]
    return {**verification.assess(card, hours, windows), "station": st,
            "method": "max PM2.5 inside the windows of concern at the nearest archived station vs the card's tier"}


def account_entity_day(entity_id: str, date: str, store: Storage | None = None, by: dict | None = None) -> dict | None:
    """Write the ImpactStatement for one entity-day from its forecast / act / check records."""
    store = store or storage()
    meta = _entities(store).get(entity_id)
    if not meta:
        return None
    kinds: dict[str, dict] = {}
    for r in records.records_for(entity_id, store):
        if (r.get("payload", {}).get("date") or r["date"]) == date and r["payload"].get("subject") != "plan":
            kinds[r["kind"]] = r
    card = (kinds.get("forecast") or {}).get("payload")
    if not card:
        return None
    ver = kinds.get("verify")
    imp = accounting.impact(card, (kinds.get("act") or {}).get("payload"), (ver or {}).get("payload"), meta)
    return records.append("account", entity_id, {**imp, "date": date}, meta.get("type", "school"), card.get("runId"), store=store, by=by)


def run_day(date: str, store: Storage | None = None, lookback_days: int = 7) -> dict:
    store = store or storage()
    entities = _entities(store)
    summary = {"date": date, "checked": 0, "pending": 0, "accounted": 0}
    for eid, meta in entities.items():
        by_date: dict[str, dict[str, dict]] = {}
        for r in records.records_for(eid, store):
            if r["payload"].get("subject") in ("plan", "registration"):
                continue
            by_date.setdefault(r.get("payload", {}).get("date") or r["date"], {})[r["kind"]] = r
        for d, kinds in by_date.items():
            if (datetime.strptime(date, "%Y-%m-%d") - datetime.strptime(d, "%Y-%m-%d")).days not in range(0, lookback_days + 1):
                continue
            card = (kinds.get("forecast") or {}).get("payload")
            if not card:
                continue
            ver = kinds.get("verify")
            if not ver or ver["payload"].get("outcome") == "pending":
                vp = check_entity_day(meta, card, d)
                if not ver or vp["outcome"] != "pending":
                    ver = records.append("verify", eid, {**vp, "date": d}, meta.get("type", "school"), card.get("runId"), store=store,
                                         by={"role": "verifier", "name": (vp.get("station") or {}).get("name", "station data") if vp.get("station") else "pending"})
                summary["checked" if vp["outcome"] != "pending" else "pending"] += 1
            if ver and ver["payload"].get("outcome") != "pending" and "account" not in kinds:
                imp = accounting.impact(card, (kinds.get("act") or {}).get("payload"), ver["payload"], meta)
                records.append("account", eid, {**imp, "date": d}, meta.get("type", "school"), card.get("runId"), store=store)
                summary["accounted"] += 1
    log.info("records daily %s", summary)
    return summary


def handler(event, context):
    logging.getLogger().setLevel(logging.INFO)
    date = (event or {}).get("date") or (utc_now().astimezone(IST) - timedelta(days=1)).strftime("%Y-%m-%d")
    return run_day(date)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=(utc_now().astimezone(IST) - timedelta(days=1)).strftime("%Y-%m-%d"))
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    print(json.dumps(run_day(a.date), indent=1))
    sys.exit(0)
