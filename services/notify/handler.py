"""NotifyFn Lambda: event = message inputs -> {hi, en, chars, source}. Invoked synchronously by the
API so the Strands dependency stays out of the API package's hot path."""
from __future__ import annotations

import logging

from notify.assess_agent import narrate
from notify.service import generate

logging.getLogger().setLevel(logging.INFO)


def handler(event, context):
    event = event or {}
    if event.get("task") == "assess":   # the choice assessment shares the function (same key, same model)
        return narrate(event)
    return generate(event)
