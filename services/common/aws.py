"""boto3 clients and the SSM secret cache. Lambdas read secrets once at cold start.

Resolution order for a secret: environment variable (local dev only) -> SSM SecureString
at `${SSM_PREFIX}${name}` -> None. Nothing secret is ever written to the repo or to
Lambda environment variables in the template (DESIGN.md §10.2).
"""
from __future__ import annotations

import functools
import logging
import os

log = logging.getLogger(__name__)

SSM_PREFIX = os.environ.get("SSM_PREFIX", "/mordor/")
REGION = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"


@functools.cache
def client(service: str):
    import boto3

    return boto3.client(service, region_name=REGION)


@functools.cache
def resource(service: str):
    import boto3

    return boto3.resource(service, region_name=REGION)


@functools.cache
def secret(name: str, env_var: str | None = None) -> str | None:
    """`name` is the SSM leaf (e.g. 'firms_map_key'); env_var defaults to its upper-case form."""
    env_var = env_var or name.upper()
    val = os.environ.get(env_var)
    if val:
        return val
    if not os.environ.get("TABLE_NAME") and not os.environ.get("DATA_BUCKET"):
        # Local run without AWS: don't even try SSM.
        return None
    try:
        resp = client("ssm").get_parameter(Name=f"{SSM_PREFIX}{name}", WithDecryption=True)
        return resp["Parameter"]["Value"]
    except Exception as exc:  # noqa: BLE001 - missing parameter is a normal state
        log.warning("secret %s unavailable: %s", name, exc)
        return None
