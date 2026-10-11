"""Lambda entry point: EventBridge Scheduler (hourly) -> OpenAQ v3 + data.gov.in -> S3 + DynamoDB."""
from __future__ import annotations

import json
import logging

from common.aws import secret
from ingest_cpcb import cpcb

logging.basicConfig(level=logging.INFO)


def handler(event, context):
    return cpcb.run(api_key=secret("data_gov_api_key"), openaq_key=secret("openaq_api_key"))


if __name__ == "__main__":
    print(json.dumps(handler({}, None), indent=2))
