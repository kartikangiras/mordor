"""Plain decision records (DESIGN.md §13.5): what was forecast, what was advised, what the
operator did, what the nearest station then measured, and what that was worth. One JSON
document per record, numbered per entity, contact-free, readable by anyone. No hashes.

  enrol     EntityRegistration   who holds the card
  forecast  ForecastCard         the card: tier, windows, peak
  advise    Advisory             the message sent (source, audience) or the plan
  act       ActionReport         what the operator did and how it was sent
  verify    OutcomeCheck         forecast vs observed at the nearest station
  account   ImpactStatement      people x protected hours, credited only when the day was confirmed
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from common import ddb
from common.storage import Storage, storage
from common.timeutil import IST, utc_now

log = logging.getLogger(__name__)
UTC = timezone.utc

SCHEMAS = {"enrol": "EntityRegistration", "forecast": "ForecastCard", "advise": "Advisory", "act": "ActionReport",
           "verify": "OutcomeCheck", "account": "ImpactStatement"}
STEPS = ["enrol", "forecast", "advise", "act", "verify", "account"]
STEP_LABELS = {"enrol": "Register", "forecast": "Forecast", "advise": "Advise", "act": "Act", "verify": "Check", "account": "Impact"}


def _ts(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _last_seq(entity: str, store: Storage) -> int:
    item = ddb.get_item(f"REC#{entity}", "HEAD")
    if item:
        return int(item.get("seq") or 0)
    keys = sorted(k for k in store.list(f"records/{entity}/") if k.endswith(".json"))
    if not keys:
        return 0
    last = store.get_json(keys[-1])
    return int(last.get("seq") or 0) if last else 0


def append(kind: str, entity: str, payload: dict, actor_type: str = "system", run_id: str | None = None,
           by: dict | None = None, store: Storage | None = None, ts: datetime | None = None) -> dict:
    """Append one record to an entity's log. payload must be contact-free."""
    assert kind in SCHEMAS, kind
    store = store or storage()
    ts = ts or utc_now()
    seq = _last_seq(entity, store) + 1
    rec = {
        "id": f"{entity}:{seq}", "schema": SCHEMAS[kind], "kind": kind, "entity": entity, "actorType": actor_type,
        "seq": seq, "ts": _ts(ts), "date": ts.astimezone(IST).strftime("%Y-%m-%d"), "runId": run_id,
        "by": by or {"role": "analyst", "name": "system"}, "payload": payload,
    }
    sk = f"{seq:06d}#{kind}"
    ddb.put_items([{"PK": f"REC#{entity}", "SK": sk, **rec, "GSI1PK": f"REC#{rec['date']}", "GSI1SK": f"{entity}#{sk}"},
                   {"PK": f"REC#{entity}", "SK": "HEAD", "seq": seq, "ts": rec["ts"], "kind": kind}])
    store.put_json(f"records/{entity}/{seq:06d}-{kind}.json", rec)
    return rec


def records_for(entity: str, store: Storage | None = None) -> list[dict]:
    store = store or storage()
    if ddb.enabled():
        items = ddb.query(f"REC#{entity}")
        out = [{k: v for k, v in i.items() if k not in ("PK", "SK", "GSI1PK", "GSI1SK")} for i in items if i.get("SK") != "HEAD"]
    else:
        keys = sorted(k for k in store.list(f"records/{entity}/") if k.endswith(".json"))
        out = [r for r in (store.get_json(k) for k in keys) if r]
    return sorted(out, key=lambda r: int(r.get("seq") or 0))


def records_for_date(date: str, store: Storage | None = None) -> list[dict]:
    store = store or storage()
    if ddb.enabled():
        return [{k: v for k, v in i.items() if k not in ("PK", "SK", "GSI1PK", "GSI1SK")} for i in ddb.query_gsi1(f"REC#{date}")]
    out = []
    for key in store.list("records/"):
        if key.endswith(".json"):
            r = store.get_json(key)
            if r and r.get("date") == date:
                out.append(r)
    return sorted(out, key=lambda r: r["ts"])


def public_view(rec: dict) -> dict:
    out = json.loads(json.dumps(rec))
    for k in ("phone", "email", "principal", "contact"):
        out.get("payload", {}).pop(k, None)
    return out
