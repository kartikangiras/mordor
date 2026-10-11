"""Step 7, Account: the impact unit per actor type, credited only when the day was verified.
No number is invented: people counts come from onboarding, hours from the card, the credit
flag from the verification record."""
from __future__ import annotations

from protocol.actors import actor_type


def impact(card: dict, act_payload: dict | None, verify_payload: dict | None, entity_meta: dict) -> dict:
    at = actor_type(card.get("actorType"))
    people = int(entity_meta.get(at["peopleField"]) or 0)
    actions = (act_payload or {}).get("actions", [])
    outcome = (verify_payload or {}).get("outcome", "pending")
    if at["kind"] == "source":
        cells = len(card.get("cells", []))
        actioned = cells if any(a in actions for a in ("dispatch_balers", "nodal_visits")) else 0
        return {"unit": at["impactUnit"], "value": actioned, "status": "provisional", "people": people,
                "method": "cells in the card that received balers or nodal visits; outcome = fires in those cells over the next 48 h vs the 2024 expectation (reported, not claimed)"}
    # coverage-weighted: each action addresses a share of the hours at risk (protocol/assess.py),
    # so a fuller set of actions earns more of the people-hours than a token one
    from protocol.assess import assess

    a = assess(card, actions, entity_meta)
    hours = a["protectedHours"]
    value = a["value"]
    status = "verified" if outcome == "confirmed" and value > 0 else "not_credited" if outcome in ("not_confirmed", "moot") else "provisional"
    return {"unit": at["impactUnit"], "value": round(value, 1), "people": people, "hours": hours, "status": status, "outcome": outcome,
            "coverage": a["coverage"], "hoursAtRisk": a["hoursAtRisk"],
            "method": f"{at['peopleField']} x hours of the windows of concern at T2 or worse x the coverage of the actions taken, credited only when the nearest station confirmed T2+"}
