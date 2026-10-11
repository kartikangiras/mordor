"""generate(inputs) -> the parent message, from cache, the agent, or the template - in that
order - and never nothing (DESIGN.md §6.4)."""
from __future__ import annotations

import hashlib
import json
import logging
import os

from common import ddb
from common.timeutil import ttl_epoch
from notify import agent, fallback, validate

log = logging.getLogger(__name__)
MSG_TTL_DAYS = 7


def cache_key(inputs: dict) -> str:
    basis = json.dumps({"school": inputs.get("schoolId"), "actor": inputs.get("actorType"), "date": inputs.get("date"), "tier": inputs.get("tier"),
                        "windows": inputs.get("windows"), "purifiers": bool(inputs.get("hasPurifiers")),
                        "actions": sorted(inputs.get("actions", []))}, sort_keys=True)
    return hashlib.sha256(basis.encode()).hexdigest()[:24]


def generate(inputs: dict, use_agent: bool | None = None) -> dict:
    """inputs: schoolId, school, date, tier, grapAnchor, windows, peakAqi, actions, hasPurifiers,
    schoolHours, dismissal. Returns {hi, en, chars, source, cacheKey}."""
    key = cache_key(inputs)
    cached = ddb.get_item(f"MSG#{key}", "V1")
    if cached and cached.get("hi") and cached.get("en"):
        return {"hi": cached["hi"], "en": cached["en"], "chars": len(cached["hi"]) + len(cached["en"]),
                "source": cached.get("source", "cache"), "cacheKey": key, "cached": True}
    if use_agent is None:
        use_agent = os.environ.get("NOTIFY_USE_AGENT", "1") == "1"
    msg = None
    if use_agent and inputs.get("tier"):
        # one draft, and one retry that is told why the first was rejected; then the template
        feedback: list[str] | None = None
        for attempt in (1, 2):
            out = agent.generate(inputs, feedback)
            if not out:
                break
            ok, reasons = validate.check(out, inputs.get("actorType", "school"))
            if ok:
                msg = {**out, "chars": len(out["hi"]) + len(out["en"]), "source": "agent"}
                break
            log.warning("agent message rejected (%s) on attempt %d", reasons, attempt)
            feedback = reasons
    if msg is None:
        if inputs.get("kind") == "source":
            msg = fallback.render_source(inputs["school"], inputs["date"], inputs.get("card") or {})
        else:
            msg = fallback.render(inputs["school"], inputs["date"], inputs.get("tier") or "T0", inputs.get("windows", []),
                                  inputs.get("peakAqi"), inputs.get("dismissal") or ("15:00", "16:00"), inputs.get("actorType", "school"))
        ok, reasons = validate.check(msg, inputs.get("actorType", "school"))
        if not ok:
            log.error("template message violates constraints: %s", reasons)
    ddb.put_item({"PK": f"MSG#{key}", "SK": "V1", "hi": msg["hi"], "en": msg["en"], "source": msg["source"],
                  "ttl": ttl_epoch(MSG_TTL_DAYS)})
    return {**msg, "cacheKey": key, "cached": False}
