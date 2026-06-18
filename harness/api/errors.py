"""FastAPI exception handlers and middleware for structured error responses."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from harness.core.errors import HarnessError, format_exception, new_correlation_id, report_error
from harness.logging_config import get_logger

logger = get_logger("api.errors")


def _correlation_id(request: Request) -> str | None:
    return getattr(request.state, "correlation_id", None)


def _format_http_detail(detail: Any) -> str:
    if isinstance(detail, str):
        return detail.strip() or "Request failed"
    if isinstance(detail, list):
        parts: list[str] = []
        for item in detail:
            if isinstance(item, dict):
                loc = ".".join(str(x) for x in item.get("loc", ()))
                msg = item.get("msg", "")
                parts.append(f"{loc}: {msg}" if loc else str(msg))
            else:
                parts.append(str(item))
        return "; ".join(p for p in parts if p) or "Validation failed"
    if isinstance(detail, dict):
        return str(detail.get("message") or detail.get("detail") or detail) or "Request failed"
    return str(detail) if detail is not None else "Request failed"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Attach a correlation id to every request/response for live debugging."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        correlation_id = request.headers.get("x-correlation-id") or new_correlation_id()
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["x-correlation-id"] = correlation_id
        return response


def register_error_handlers(app: FastAPI) -> None:
    """Register global handlers so no API failure returns a blank error."""

    @app.exception_handler(HarnessError)
    async def harness_error_handler(request: Request, exc: HarnessError) -> JSONResponse:
        body = exc.to_dict(correlation_id=_correlation_id(request))
        return JSONResponse(status_code=exc.status_code, content=body)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        message = _format_http_detail(exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": f"HTTP_{exc.status_code}",
                "message": message,
                "detail": message,
                "correlation_id": _correlation_id(request),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        message = _format_http_detail(exc.errors())
        return JSONResponse(
            status_code=422,
            content={
                "code": "VALIDATION_ERROR",
                "message": message,
                "detail": message,
                "correlation_id": _correlation_id(request),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        message = format_exception(exc, fallback="Internal server error")
        try:
            from harness.api.main import get_harness

            harness = get_harness()
            await report_error(
                harness.observer,
                exc,
                source="api",
                code="INTERNAL_ERROR",
                message=message,
            )
        except Exception:
            logger.exception("api_error_report_failed", error=message)
        return JSONResponse(
            status_code=500,
            content={
                "code": "INTERNAL_ERROR",
                "message": message,
                "detail": message,
                "correlation_id": _correlation_id(request),
            },
        )
