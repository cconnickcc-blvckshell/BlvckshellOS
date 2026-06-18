"""Conversation history schemas for Blvckbot persistent memory."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


def _now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


class ConversationEntry(BaseModel):
    """A single message in an operator conversation."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    role: str
    brain_id: str | None = None
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now)


class ConversationSession(BaseModel):
    """Summary metadata for a conversation session."""

    session_id: str
    operator_id: str = "operator"
    created_at: datetime = Field(default_factory=_now)
    message_count: int = 0
