"""Lambda entry point: EventBridge Scheduler -> Open-Meteo -> S3 (+ DynamoDB log)."""
from __future__ import annotations

import json
import logging

from ingest_weather import openmeteo

logging.basicConfig(level=logging.INFO)


def handler(event, context):
    return openmeteo.run()


if __name__ == "__main__":
    print(json.dumps(handler({}, None), indent=2))
