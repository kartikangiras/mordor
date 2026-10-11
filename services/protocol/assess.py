"""What a choice does (PIVOT_PLAN.md task 38). Each action carries a weight: the share of the
hours at risk it addresses; coverage is the capped sum over the actions chosen. Every number
traces to the card (hours at Very Poor or worse inside the windows of concern), the onboarding
(people) and the weights table in actors.py. Claude writes the words; the arithmetic is here."""
from __future__ import annotations

from protocol.actors import actor_type


def assess(card: dict, actions: list[str], meta: dict) -> dict:
    at = actor_type(card.get("actorType"))
    valid = {a["id"]: a for a in at["actions"]}
    chosen = [valid[a] for a in actions if a in valid]
    coverage = min(1.0, round(sum(float(a.get("weight") or 0) for a in chosen), 2))
    people = int(meta.get(at["peopleField"]) or 0)
    missing = sorted(({"id": a["id"], "label": a["label"], "weight": float(a.get("weight") or 0)} for a in at["actions"] if a["id"] not in {c["id"] for c in chosen}),
                     key=lambda m: -m["weight"])
    base = {"kind": at["kind"], "actorType": at["id"], "tier": card.get("dayTier"), "peakAqi": card.get("peakAqi"), "date": card.get("date"),
            "coverage": coverage, "people": people, "unit": at["impactUnit"], "chosen": [c["id"] for c in chosen], "missing": missing}
    if at["kind"] == "source":
        cells = card.get("cells") or []
        at_risk = [c for c in cells if c.get("category") in ("High", "Extreme")] or cells
        actioned = len(at_risk) if any(c["id"] in ("dispatch_balers", "nodal_visits") for c in chosen) else 0
        return {**base, "cellsAtRisk": len(at_risk), "cellsActioned": actioned, "value": actioned}
    hours = float(card.get("outdoorHoursCancelled") or 0)
    protected = round(hours * coverage, 1)
    return {**base, "hoursAtRisk": hours, "protectedHours": protected, "exposedHours": round(hours - protected, 1), "value": round(people * protected, 1)}


def fallback_text(a: dict, name: str) -> str:
    """The assessment in plain English when no model answers: the same facts, no judgement."""
    tier = {"T0": "Normal", "T1": "Poor", "T2": "Very Poor", "T3": "Severe", "T4": "Severe+"}.get(a.get("tier") or "", "not forecast")
    add = f" Add: {a['missing'][0]['label'].lower()}." if a.get("missing") else " Nothing left to add."
    if a["kind"] == "source":
        return (f"{name}: {a['cellsActioned']} of {a['cellsAtRisk']} high-risk cells get balers or nodal officers under this plan.{add}")
    if not a["hoursAtRisk"]:
        return (f"{name}: tomorrow is {tier} with no hours at Very Poor or worse in the windows of concern, so these actions protect nothing today; "
                f"they cover {int(a['coverage'] * 100)}% of the risk if the evening worsens.{add}")
    return (f"{name}: {a['protectedHours']} of {a['hoursAtRisk']} hours at risk are covered for {a['people']:,} people ({a['value']:,.0f} {a['unit']}); "
            f"{a['exposedHours']} hours stay exposed.{add}")
