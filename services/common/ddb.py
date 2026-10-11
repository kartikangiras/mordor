"""Single-table DynamoDB helpers (DESIGN.md §7.1). When TABLE_NAME is unset (local dev) every
write is a logged no-op and every read returns nothing, so callers must not depend on the
index for correctness - the S3 raw files are the truth, DynamoDB is the index."""
from __future__ import annotations

import logging
import os
from collections.abc import Iterable
from decimal import Decimal
from typing import Any

log = logging.getLogger(__name__)

_TABLE = None


def enabled() -> bool:
    return bool(os.environ.get("TABLE_NAME"))


def table():
    global _TABLE
    if _TABLE is None and enabled():
        from common.aws import resource

        _TABLE = resource("dynamodb").Table(os.environ["TABLE_NAME"])
    return _TABLE


def to_ddb(value: Any) -> Any:
    """Recursively convert floats to Decimal (DynamoDB rejects float)."""
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return None
        return Decimal(repr(value))
    if isinstance(value, dict):
        return {k: to_ddb(v) for k, v in value.items() if v is not None}
    if isinstance(value, (list, tuple)):
        return [to_ddb(v) for v in value]
    return value


def from_ddb(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {k: from_ddb(v) for k, v in value.items()}
    if isinstance(value, list):
        return [from_ddb(v) for v in value]
    return value


def put_items(items: Iterable[dict]) -> int:
    items = list(items)
    t = table()
    if t is None:
        log.info("TABLE_NAME unset: skipping %d DynamoDB writes", len(items))
        return 0
    with t.batch_writer(overwrite_by_pkeys=["PK", "SK"]) as batch:
        for it in items:
            batch.put_item(Item=to_ddb(it))
    return len(items)


def put_item(item: dict) -> None:
    put_items([item])


def get_item(pk: str, sk: str) -> dict | None:
    t = table()
    if t is None:
        return None
    resp = t.get_item(Key={"PK": pk, "SK": sk})
    item = resp.get("Item")
    return from_ddb(item) if item else None


def query(pk: str, sk_prefix: str | None = None, limit: int | None = None,
          scan_forward: bool = True) -> list[dict]:
    t = table()
    if t is None:
        return []
    from boto3.dynamodb.conditions import Key

    cond = Key("PK").eq(pk)
    if sk_prefix:
        cond = cond & Key("SK").begins_with(sk_prefix)
    kwargs: dict[str, Any] = {"KeyConditionExpression": cond, "ScanIndexForward": scan_forward}
    if limit:
        kwargs["Limit"] = limit
    out: list[dict] = []
    while True:
        resp = t.query(**kwargs)
        out.extend(from_ddb(i) for i in resp.get("Items", []))
        lek = resp.get("LastEvaluatedKey")
        if not lek or (limit and len(out) >= limit):
            break
        kwargs["ExclusiveStartKey"] = lek
    return out


def query_gsi1(gsi1pk: str, sk_prefix: str | None = None) -> list[dict]:
    """Query GSI1 (e.g. DATE#2026-10-09 -> every school's decision log for that day)."""
    t = table()
    if t is None:
        return []
    from boto3.dynamodb.conditions import Key

    cond = Key("GSI1PK").eq(gsi1pk)
    if sk_prefix:
        cond = cond & Key("GSI1SK").begins_with(sk_prefix)
    out: list[dict] = []
    kwargs: dict[str, Any] = {"IndexName": "GSI1", "KeyConditionExpression": cond}
    while True:
        resp = t.query(**kwargs)
        out.extend(from_ddb(i) for i in resp.get("Items", []))
        lek = resp.get("LastEvaluatedKey")
        if not lek:
            break
        kwargs["ExclusiveStartKey"] = lek
    return out


# --- key builders (keep in sync with DESIGN.md §7.1) ------------------------------------------
def fire_pk(date_str: str) -> str:
    return f"FIRE#{date_str}"


def fire_sk(acq_iso: str, lat: float, lon: float) -> str:
    return f"{acq_iso}#{lat:.5f}#{lon:.5f}"


def station_pk(station_id: str) -> str:
    return f"STATION#{station_id}"


def obs_sk(hour_iso: str) -> str:
    return f"OBS#{hour_iso}"


RUN_PK = "RUN"
LATEST_SK = "LATEST"
INGEST_PK = "INGEST"
