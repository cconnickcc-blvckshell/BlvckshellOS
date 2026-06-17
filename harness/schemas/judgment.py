"""Judgment Ledger schema — LOCKED V1. Do not modify the field set.

The Judgment Ledger is the system's memory of *why* it believed what it
believed, and whether reality agreed. It is the substrate the harness will one
day train on.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _new_id() -> str:
    """Generate a fresh UUID4 string for a ledger entry id."""
    return str(uuid4())


def _utcnow() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


class JudgmentChange(BaseModel):
    """A single appended change in a ledger entry's changelog.

    Attributes:
        timestamp: When the change was made (UTC).
        actor: ``brain_id`` or subsystem that made the change.
        field: The field that changed.
        note: Free-form description of the change.
    """

    timestamp: datetime = Field(default_factory=_utcnow)
    actor: str
    field: str
    note: str


class JudgmentEntry(BaseModel):
    """A single belief recorded by a brain — LOCKED V1 schema.

    Attributes:
        id: UUID for the entry.
        brain_id: The brain that holds this belief.
        context_id: Pipeline run this belief was formed in.
        timestamp: When the belief was recorded (UTC).
        belief: What the brain believes / decided.
        confidence: Confidence in the belief, 0.0 - 1.0.
        evidence: What supported this belief.
        assumptions: What was assumed to hold.
        contradicts: IDs of beliefs this one contradicts.
        outcome: Filled in once the real-world result is known.
        outcome_timestamp: When the outcome was recorded.
        was_correct: Whether the belief proved correct.
        doctrine_promoted: Whether this became validated doctrine.
        retired: Whether this belief has been superseded.
        changelog: Full append-only history of changes.
    """

    id: str = Field(default_factory=_new_id)
    brain_id: str
    context_id: str
    timestamp: datetime = Field(default_factory=_utcnow)
    belief: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    contradicts: list[str] = Field(default_factory=list)
    outcome: str | None = None
    outcome_timestamp: datetime | None = None
    was_correct: bool | None = None
    doctrine_promoted: bool = False
    retired: bool = False
    changelog: list[dict[str, Any]] = Field(default_factory=list)

    def record_change(self, *, actor: str, field: str, note: str) -> None:
        """Append a change to the immutable changelog.

        Args:
            actor: Who made the change (``brain_id`` or subsystem name).
            field: The field affected.
            note: Description of what changed and why.
        """
        self.changelog.append(
            JudgmentChange(actor=actor, field=field, note=note).model_dump(mode="json")
        )
