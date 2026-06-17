"""Audit event schema for the Observer.

Every meaningful thing that happens in the harness becomes an
:class:`AuditEvent`. This is the system's flight recorder.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def _now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


class AuditEventType(str, Enum):
    """Every category of event the Observer records."""

    MESSAGE_SENT = "MESSAGE_SENT"
    MESSAGE_RECEIVED = "MESSAGE_RECEIVED"
    BRAIN_REGISTERED = "BRAIN_REGISTERED"
    BRAIN_DEREGISTERED = "BRAIN_DEREGISTERED"
    BRAIN_HEARTBEAT = "BRAIN_HEARTBEAT"
    TASK_STARTED = "TASK_STARTED"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_FAILED = "TASK_FAILED"
    LLM_CALL = "LLM_CALL"
    TOOL_CALL = "TOOL_CALL"
    JUDGMENT_CREATED = "JUDGMENT_CREATED"
    JUDGMENT_UPDATED = "JUDGMENT_UPDATED"
    DOCTRINE_PROMOTED = "DOCTRINE_PROMOTED"
    PIPELINE_STARTED = "PIPELINE_STARTED"
    PIPELINE_COMPLETED = "PIPELINE_COMPLETED"
    ERROR = "ERROR"


class AuditEvent(BaseModel):
    """A single immutable record of something that happened in the harness.

    Attributes:
        id: Unique identifier for the event.
        timestamp: When the event occurred (UTC).
        event_type: The category of event.
        source: The component or ``brain_id`` that produced the event.
        context_id: The pipeline run this event belongs to, if any.
        message: A short human-readable description.
        data: Structured detail (model, tokens, cost, latency, payloads, ...).
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=_now)
    event_type: AuditEventType
    source: str
    context_id: str | None = None
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
