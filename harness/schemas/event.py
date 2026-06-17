"""Observer event schema — the atomic unit of the audit log."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _new_id() -> str:
    """Generate a fresh UUID4 string for an event id."""
    return str(uuid4())


def _utcnow() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


class EventType(str, Enum):
    """Every kind of event the observer records.

    The observer audits everything; this enum is the closed set of things that
    can happen in the harness.
    """

    MESSAGE_SENT = "message_sent"
    MESSAGE_RECEIVED = "message_received"
    BRAIN_REGISTERED = "brain_registered"
    BRAIN_DEREGISTERED = "brain_deregistered"
    BRAIN_HEARTBEAT = "brain_heartbeat"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"
    JUDGMENT_CREATED = "judgment_created"
    JUDGMENT_UPDATED = "judgment_updated"
    DOCTRINE_PROMOTED = "doctrine_promoted"
    PIPELINE_STARTED = "pipeline_started"
    PIPELINE_COMPLETED = "pipeline_completed"
    ERROR = "error"


class ObserverEvent(BaseModel):
    """A single immutable audit-log record.

    Attributes:
        id: UUID for the event.
        timestamp: When it occurred (UTC).
        event_type: One of :class:`EventType`.
        source: Subsystem or ``brain_id`` that emitted it.
        context_id: Pipeline run the event belongs to, if applicable.
        message: Human-readable description.
        data: Structured event detail (tokens, cost, latency, ids, ...).
    """

    id: str = Field(default_factory=_new_id)
    timestamp: datetime = Field(default_factory=_utcnow)
    event_type: EventType
    source: str
    context_id: str | None = None
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
