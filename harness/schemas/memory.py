"""Personal memory schemas — durable notes and self-revising opinions.

This is a fourth tier of memory, parallel to the Judgment Ledger and Doctrine,
but scoped to the operator relationship rather than task correctness. Notes
are durable summaries of what was discussed; opinions are synthesized,
explicitly revisable standing positions the system has formed, each carrying
its own reasoning, confidence, and full revision history.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


def _now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


class MemoryNote(BaseModel):
    """A durable summary or excerpt distilled from a conversation.

    Attributes:
        id: Unique identifier for this note.
        session_id: The conversation session this note was distilled from.
        operator_id: Who the note pertains to.
        content: The note text itself.
        topics: Short topic tags for coarse filtering.
        embedding: Vector embedding of ``content``, for semantic recall.
        created_at: When the note was written.
        source_entry_ids: Conversation entry ids this note was derived from.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    operator_id: str | None = None
    content: str
    topics: list[str] = Field(default_factory=list)
    embedding: list[float] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)
    source_entry_ids: list[str] = Field(default_factory=list)


class Opinion(BaseModel):
    """A synthesized, explicitly revisable standing position.

    Unlike doctrine (which is append-only and validated against outcomes),
    an opinion is a belief about the operator, the project, or the world that
    the system forms from accumulated notes and conversation, and can later
    revise or retract as it learns more — mirroring how a person's views
    change. Revision never destroys history: the prior opinion is retired and
    linked to the entry that superseded it.

    Attributes:
        id: Unique identifier for this opinion.
        operator_id: Who/what this opinion is about or held for.
        topic: Short label for what this opinion concerns.
        statement: The position itself, stated plainly.
        reasoning: Why the system holds this position.
        confidence: Confidence in the position, ``0.0``-``1.0``.
        embedding: Vector embedding of ``statement``, for semantic recall.
        source_note_ids: Notes that informed this opinion.
        supersedes: The id of the opinion this one revises, if any.
        superseded_by: The id of the opinion that replaced this one, if any.
        retired: Whether this opinion has been superseded.
        created_at: When this opinion was first formed.
        changelog: Full history of changes to this opinion.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    operator_id: str | None = None
    topic: str
    statement: str
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)
    embedding: list[float] = Field(default_factory=list)
    source_note_ids: list[str] = Field(default_factory=list)
    supersedes: str | None = None
    superseded_by: str | None = None
    retired: bool = False
    created_at: datetime = Field(default_factory=_now)
    changelog: list[dict[str, Any]] = Field(default_factory=list)

    def record_change(self, action: str, details: dict[str, Any] | None = None) -> None:
        """Append an entry to this opinion's changelog.

        Args:
            action: A short label describing what changed.
            details: Optional structured detail about the change.
        """
        self.changelog.append(
            {
                "action": action,
                "timestamp": _now().isoformat(),
                "details": details or {},
            }
        )
