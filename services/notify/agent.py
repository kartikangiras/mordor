"""Strands Agents SDK (AWS open source) writes the bilingual parent message (DESIGN.md §6.4).
Strict JSON via a pydantic structured output; every output is re-validated in code and silently
replaced by the template if it breaks a constraint; the per-day cache keeps re-renders identical.

Model provider, chosen once per cold start (`NOTIFY_PROVIDER`: auto | anthropic | bedrock):
- **Anthropic API** when the SSM SecureString `/mordor/anthropic_api_key` exists (locally:
  `ANTHROPIC_API_KEY`): Strands' `AnthropicModel` on `NOTIFY_ANTHROPIC_MODEL`, default Claude
  Haiku 4.5 (Sonnet 5 is selectable; measured slower and over the length limit). This is the deployed path — the hackathon account cannot use Anthropic models on
  Bedrock, and the Anthropic credits cover a card message many thousands of times over.
- otherwise the Jinja template. **Amazon Bedrock** on `NOTIFY_MODEL_ID` (default Amazon Nova Lite)
  only when `NOTIFY_PROVIDER=bedrock` is set explicitly, with fail-fast client timeouts.
Both ride the same tool use that `structured_output_model` needs, so the agent code is shared.
The key is read through `common.aws.secret` (never an env var in the template, never logged).
"""
from __future__ import annotations

import logging
import os

from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"   # measured 2026-10-10: ~4 s, within the 400-char limit; Sonnet 5 was slow (thinking) or verbose
DEFAULT_MODEL_ID = "us.amazon.nova-lite-v1:0"  # Bedrock cross-region profile, Amazon first-party

SYSTEM = """You write one short WhatsApp message about tomorrow's air quality, from the sender named in the request (a school, a residents' association, a district agriculture office or a hospital) to the audience named there. Speak as that sender: a residents' association talks about the colony, the park and the gates, never about a school; a hospital talks to its wards about stock, oxygen, beds and the helpline.
Hard rules, all of them:
- Hindi first, then English. Both plain, warm, factual. Keep it short: two sentences each, about 300 characters for Hindi and English together, never more than 380.
- Start the Hindi text with exactly one marker emoji (🌫 or 🌤). No other emoji anywhere: the English text contains no emoji at all.
- Always name at least one concrete clock time: the times you are given (for example "10 बजे से"), and on a normal day with no hours of concern, the pickup time ("3 pm pickup").
- Give parents exactly ONE action (for example send a mask for the pickup, or send a water bottle).
- Never use the word "emergency" or "आपातकाल", and never mention medicines, inhalers or doses - except a hospital writing to its own wards, which names its emergency ward and its stock of inhalers, nebulisers and oxygen.
- Never say or imply that the school or the colony is closed or that a holiday is declared, and never use the words "closed", "closure" or "holiday" in any form, not even for windows or gates (say "shut"). For Stage IV a school says it is watching for the Directorate of Education order; an association says it is watching for CAQM orders.
- Do not add greetings, signatures, links or hashtags.
Respond by calling the ParentMessage tool with the fields hi and en; write nothing else."""


class ParentMessage(BaseModel):
    hi: str = Field(description="Hindi message, starts with one marker emoji")
    en: str = Field(description="English message")


def _prompt(inputs: dict, feedback: list[str] | None = None) -> str:
    note = f"\nYour previous draft was rejected for: {'; '.join(feedback)}. Write it again and fix exactly that." if feedback else ""
    audience = {"rwa": "residents of a housing society", "agri_officer": "custom hiring centres and village volunteers",
                "hospital": "the hospital's emergency and respiratory ward staff (medicine stock, oxygen, beds, helpline)"}.get(inputs.get("actorType", "school"), "parents")
    if inputs.get("kind") == "source":
        card = inputs.get("card") or {}
        cells = "; ".join(f"{c['name']} score {c['score']} {c['category']} ({c.get('fires24', 0)} fires/24h)" for c in card.get("cells", [])[:6])
        return (f"Audience: {audience}. Sender: {inputs['school']} (district agriculture office).\nDate: {inputs['date']}\n"
                f"Cells most likely to burn in the next 48 h: {cells or 'none'}\nAlready burning: {card.get('burningNow', 0)} cells\n"
                f"Actions the office is taking: {', '.join(inputs.get('actions', [])) or 'none'}\n"
                "Write the message: Hindi then English, name the top areas, ask for ONE thing (machine availability by a named time)." + note)
    windows = "; ".join(f"{w['fromIst']}-{w['toIst']} {w['tier']} (AQI up to {w.get('peakAqi')})" for w in inputs.get("windows", []))
    return (f"Audience: {audience}. Sender: {inputs['school']}\nDate: {inputs['date']}\nDay tier: {inputs['tier']} ({inputs.get('grapAnchor', '')})\n"
            f"Hourly windows (IST): {windows or 'none'}\nSchool hours: {inputs.get('schoolHours')} dismissal {inputs.get('dismissal')}\n"
            f"Actions the school is taking: {', '.join(inputs.get('actions', [])) or 'none'}\n"
            f"Has air purifiers: {inputs.get('hasPurifiers', False)}\nWrite the message." + note)


def provider() -> str:
    """Which provider a call would use right now: 'anthropic', 'bedrock' or 'none'.

    `auto` is Anthropic when the key exists, otherwise none (the template): Bedrock is only
    ever used on an explicit NOTIFY_PROVIDER=bedrock, because on an account where the model
    is not served the call retries until the Lambda's 60 s timeout, and the API that waits
    for it dies at 30 s with no card at all (seen live, 2026-10-10).
    """
    want = os.environ.get("NOTIFY_PROVIDER", "auto")
    if want == "bedrock":
        return "bedrock"
    from common.aws import secret
    return "anthropic" if secret("anthropic_api_key") else "none"


def _model():
    """The Strands model for the chosen provider, or None when none is usable."""
    which = provider()
    if which == "anthropic":
        from strands.models.anthropic import AnthropicModel

        from common.aws import secret

        # No temperature: Claude Sonnet 5 rejects it ("deprecated for this model"); the per-day cache
        # in service.py is what keeps re-renders identical. max_tokens covers the model's thinking
        # block plus the ~400-character tool call.
        return AnthropicModel(
            client_args={"api_key": secret("anthropic_api_key"), "max_retries": 2, "timeout": 40.0},
            model_id=os.environ.get("NOTIFY_ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL),
            max_tokens=2000,
        ), which
    if which == "bedrock":
        from botocore.config import Config as BotoConfig
        from strands.models import BedrockModel

        return BedrockModel(
            model_id=os.environ.get("NOTIFY_MODEL_ID", DEFAULT_MODEL_ID),
            region_name=os.environ.get("NOTIFY_MODEL_REGION", os.environ.get("AWS_REGION", "us-east-1")),
            temperature=0.0,
            max_tokens=600,
            # fail fast: one attempt, short timeouts, so a model that is not served answers in seconds
            boto_client_config=BotoConfig(connect_timeout=3, read_timeout=12, retries={"max_attempts": 1}),
        ), which
    return None, which


def generate(inputs: dict, feedback: list[str] | None = None) -> dict | None:
    """Returns {"hi","en"} or None on any failure (the caller falls back to the template).
    `feedback` carries the validator's reasons for a rejected first draft, for one retry."""
    try:
        from strands import Agent
    except ImportError as exc:  # pragma: no cover - local dev without strands
        log.warning("strands not installed: %s", exc)
        return None
    try:
        model, which = _model()
        if model is None:
            log.warning("no model provider configured (%s); using template", which)
            return None
        agent = Agent(model=model, system_prompt=SYSTEM, callback_handler=None)
        result = agent(_prompt(inputs, feedback), structured_output_model=ParentMessage)
        out = getattr(result, "structured_output", None)
        if out is None:
            return None
        log.info("parent message written via %s", which)
        return {"hi": out.hi.strip(), "en": out.en.strip()}
    except Exception as exc:  # noqa: BLE001 - any agent failure means "use the template"
        log.warning("strands agent failed, using template: %s", type(exc).__name__)
        return None
