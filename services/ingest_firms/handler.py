"""Lambda entry point: EventBridge Scheduler -> fetch FIRMS -> S3 + DynamoDB."""
from __future__ import annotations

import json
import logging

from common.aws import secret
from ingest_firms import firms

logging.basicConfig(level=logging.INFO)


def handler(event, context):
    return firms.run(map_key=secret("firms_map_key"))


if __name__ == "__main__":
    print(json.dumps(handler({}, None), indent=2))
