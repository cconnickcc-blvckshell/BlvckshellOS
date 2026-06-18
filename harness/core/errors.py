"""Centralized error handling and reporting for the harness.

Every failure path should produce a non-empty, actionable message. Structured
:class:`HarnessError` instances power API responses; :func:`report_error`
feeds the Observer and structured logs for live debugging.
"""

from __future__ import annotations

import uuid
from typing import Any

from harness.core.observer import Observer
from harness.logging_config import get_logger
from harness.schemas.audit import AuditEventType

logger = get_logger("errors")


def format_exception(exc: BaseException | None, *, fallback: str = "Unknown error") -> str:
    """Return a non-empty human-readable description of an exception."""
    if exc is None:
        return fallback
    msg = str(exc).strip()
    if msg:
        return msg
    return f"{type(exc).__name__}: {fallback}"


def new_correlation_id() -> str:
    """Generate a correlation id for tracing a single HTTP request."""
    return str(uuid.uuid4())


class HarnessError(Exception):
    """Structured application error with a stable code and human-readable message."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "HARNESS_ERROR",
        source: str = "harness",
        context_id: str | None = None,
        cause: BaseException | None = None,
        data: dict[str, Any] | None = None,
        status_code: int = 500,
    ) -> None:
        clean = message.strip() or format_exception(cause, fallback="Harness error")
        super().__init__(clean)
        self.message = clean
        self.code = code
        self.source = source
        self.context_id = context_id
        self.cause = cause
        self.data = data or {}
        self.status_code = status_code

    def to_dict(self, *, correlation_id: str | None = None) -> dict[str, Any]:
        """Serialize for JSON API responses."""
        detail = self.message
        if self.cause is not None:
            cause_msg = format_exception(self.cause)
            if cause_msg and cause_msg not in detail:
                detail = f"{detail} — {cause_msg}"
        return {
            "code": self.code,
            "message": self.message,
            "detail": detail,
            "source": self.source,
            "context_id": self.context_id,
            "correlation_id": correlation_id,
            "data": self.data,
        }


async def report_error(
    observer: Observer,
    exc: BaseException,
    *,
    source: str,
    context_id: str | None = None,
    code: str | None = None,
    message: str | None = None,
    event_type: AuditEventType = AuditEventType.ERROR,
    data: dict[str, Any] | None = None,
) -> None:
    """Log an exception with stack trace and emit an Observer audit event."""
    error_type = type(exc).__name__
    error_message = format_exception(exc)
    payload: dict[str, Any] = {
        "error_type": error_type,
        "error_code": code or "UNHANDLED",
        **(data or {}),
    }
    if exc.__cause__ is not None:
        payload["cause"] = format_exception(exc.__cause__)

    logger.exception(
        "harness_error",
        source=source,
        context_id=context_id,
        code=code,
        error_type=error_type,
        error=error_message,
    )

    await observer.record(
        event_type,
        source=source,
        context_id=context_id,
        message=message or error_message,
        data=payload,
    )
