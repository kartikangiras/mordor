"""Who is calling? Cognito JWT claims from the API Gateway authorizer (DESIGN.md §8, §10.1),
or - only when DEV_AUTH_BYPASS=1, set by the template's DemoAuth parameter on demo stacks - the
X-Dev-School-Id / X-Dev-Role headers the walkthrough personas send."""
from __future__ import annotations

import os

from fastapi import Request

from api.errors import ApiError
from protocol.actors import persona_for_email


def principal(request: Request) -> dict:
    event = request.scope.get("aws.event") or {}
    claims = (((event.get("requestContext") or {}).get("authorizer") or {}).get("jwt") or {}).get("claims") or {}
    school_id = claims.get("custom:school_id")
    role = claims.get("custom:role") or ("operator" if school_id else None)
    if claims.get("sub") and role:
        return {"sub": claims.get("sub"), "email": claims.get("email"), "schoolId": school_id, "entityId": school_id, "role": role, "dev": False,
                "persona": persona_for_email(claims.get("email"))}
    if os.environ.get("DEV_AUTH_BYPASS") == "1":
        dev_id = request.headers.get("x-dev-school-id")
        dev_role = request.headers.get("x-dev-role") or ("operator" if dev_id else None)
        if dev_role:
            return {"sub": f"dev:{dev_role}:{dev_id or '-'}", "email": None, "schoolId": dev_id, "entityId": dev_id, "role": dev_role, "dev": True, "persona": None}
    raise ApiError(401, "unauthorized", "Sign in to use this endpoint.")


def require_role(who: dict, *roles: str) -> None:
    if who.get("role") not in roles:
        raise ApiError(403, "forbidden", f"This endpoint needs one of the roles {list(roles)}; you are {who.get('role')!r}.")
