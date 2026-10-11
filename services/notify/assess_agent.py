"""The assessment (PIVOT_PLAN.md task 38): three plain sentences for the person who chose the
actions - what tomorrow looks like with them, what stays exposed, the one action to add. The
numbers come in from protocol/assess.py; the model only puts them into words."""
from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from notify import agent
from protocol.assess import fallback_text

log = logging.getLogger(__name__)
TIER_WORDS = {"T0": "Normal", "T1": "Poor", "T2": "Very Poor", "T3": "Severe", "T4": "Severe+"}

SYSTEM = """You assist the person who holds an air-quality card (a school principal, a residents' association secretary, a district agriculture officer or a hospital's medical superintendent) after they chose their actions for tomorrow.
You are given tomorrow's forecast for them, the people they cover, the actions chosen, and the computed share of the hours at risk those actions cover. Write exactly three short sentences in English, for that person:
1. what tomorrow looks like for them with these actions, naming the tier and the hours;
2. what is still exposed, in people and hours - or that nothing is;
3. the single most useful action to add, by its name - or that the set is complete.
Plain and specific. Use only the numbers you are given and only the words given for the air (Normal, Poor, Very Poor, Severe, Severe+) and for the actions - never a code like T2 or an identifier with underscores. If the hours at risk are zero, say that tomorrow needs no protection and that the actions chosen are ready if the evening worsens. No emoji, no greetings, at most 450 characters. Never say or imply that a school or colony is closed. Respond by calling the Assessment tool."""


class Assessment(BaseModel):
    en: str = Field(description="Three short English sentences")


def _prompt(inputs: dict) -> str:
    from protocol.actors import actor_type

    a = inputs.get("assessment") or {}
    labels = {x["id"]: x["label"] for x in actor_type(a.get("actorType"))["actions"]}
    chosen = [labels.get(i, i) for i in (a.get("chosen") or [])]
    lines = [f"Sender: {inputs.get('name')} ({a.get('actorType')})", f"Tomorrow: {a.get('date')} · air {TIER_WORDS.get(a.get('tier') or '', 'not forecast')} · peak AQI {a.get('peakAqi')}",
             f"People covered: {a.get('people')}", f"Actions chosen: {'; '.join(chosen) or 'none'}",
             f"Coverage of the hours at risk by these actions: {int(float(a.get('coverage') or 0) * 100)}%"]
    if a.get("kind") == "source":
        lines.append(f"High-risk cells: {a.get('cellsAtRisk')} · cells that get balers or officers: {a.get('cellsActioned')}")
    else:
        lines.append(f"Hours at risk (Very Poor or worse in the windows of concern): {a.get('hoursAtRisk')} · protected {a.get('protectedHours')} · still exposed {a.get('exposedHours')}")
        lines.append(f"People-hours protected by these actions: exactly {a.get('value')} {a.get('unit')} (this is the only people-hours figure; the people count is not an hours figure)")
    if a.get("missing"):
        lines.append("Not chosen (most useful first): " + "; ".join(f"{m['label']} ({int(m['weight'] * 100)}%)" for m in a["missing"][:3]))
    return "\n".join(lines) + "\nWrite the three sentences."


def narrate(inputs: dict) -> dict:
    """Returns {"en", "source"}; the template on any failure, so the box is never empty."""
    name = inputs.get("name") or "This entity"
    fb = {"en": fallback_text(inputs.get("assessment") or {"kind": "exposure", "hoursAtRisk": 0, "coverage": 0, "missing": []}, name), "source": "template"}
    try:
        from strands import Agent
        model, which = agent._model()
        if model is None:
            return fb
        r = Agent(model=model, system_prompt=SYSTEM, callback_handler=None)(_prompt(inputs), structured_output_model=Assessment)
        out = getattr(r, "structured_output", None)
        if out is None or not out.en.strip() or len(out.en) > 520:
            return fb
        log.info("assessment written via %s", which)
        return {"en": out.en.strip(), "source": "agent"}
    except Exception as exc:  # noqa: BLE001
        log.warning("assessment agent failed, using template: %s", type(exc).__name__)
        return fb
