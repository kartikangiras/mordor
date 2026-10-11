"""FastAPI app + Mangum adapter. One Lambda behind API Gateway HTTP API and CloudFront /api/*."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from mangum import Mangum
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.routes import principal, public

logging.getLogger().setLevel(logging.INFO)

app = FastAPI(title="mordor api", docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(public.router)
app.include_router(principal.router)


@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, exc: StarletteHTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "http_error", "message": str(exc.detail)}
    return JSONResponse({"error": detail}, status_code=exc.status_code, headers={"Cache-Control": "no-store"})


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    return JSONResponse(
        {"error": {"code": "bad_request", "message": str(exc)}},
        status_code=400,
        headers={"Cache-Control": "no-store"},
    )


@app.middleware("http")
async def default_cache_header(request: Request, call_next):
    """Every response carries an explicit Cache-Control (§8 conventions)."""
    response = await call_next(request)
    response.headers.setdefault("Cache-Control", "no-store")
    return response


handler = Mangum(app, lifespan="off")
