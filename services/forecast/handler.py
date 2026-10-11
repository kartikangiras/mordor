"""All-in-one Lambda entry: the five steps in one invocation (for `sam local invoke` and as a
fallback if the state machine is unavailable). The state machine calls forecast.steps.*_handler."""
from __future__ import annotations

import logging

from common.storage import storage
from forecast import steps

logging.getLogger().setLevel(logging.INFO)


def handler(event, context):
    store = storage()
    return steps.run_all(store, store, hours=int((event or {}).get("hours", 48)))
