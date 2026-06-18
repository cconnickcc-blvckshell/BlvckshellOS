"""Judgment Ledger entry schema — LOCKED V1.

This schema is the canonical record of what a brain believed, why, and whether
it turned out to be correct. It is the substrate from which validated doctrine
is eventually promoted. The shape of :class:`JudgmentEntry` is locked at v1 and
must not be modified.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


def _now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


class JudgmentEntry(BaseModel):
    """A single belief recorded by a brain in the Judgment Ledger.

    Attributes:
        id: Unique identifier for this belief.
        brain_id: The brain that holds the belief.
        context_id: The pipeline run this belief belongs to.
        timestamp: When the belief was recorded (UTC).
        belief: What the brain believes or decided.
        confidence: Confidence in the belief, ``0.0``-``1.0``.
        evidence: What supported this belief.
        assumptions: What was assumed when forming the belief.
        contradicts: IDs of beliefs this one contradicts.
        outcome: Filled in once the real-world result is known.
        outcome_timestamp: When the outcome was recorded.
        was_correct: Whether the belief proved correct.
        doctrine_promoted: Whether this has become validated doctrine.
        retired: Whether this belief has been superseded.
        changelog: Full history of changes to this entry.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    brain_id: str
    context_id: str
    timestamp: datetime = Field(default_factory=_now)
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

    def record_change(self, action: str, details: dict[str, Any] | None = None) -> None:
        """Append an entry to this belief's changelog.

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


class OutcomeRecord(BaseModel):
    """Real-world outcome attached to a judgment entry — extends ledger via changelog."""

    actual_outcome: str
    outcome_quality: float = Field(ge=-1.0, le=1.0)
    missed_opportunity: str | None = None
    lessons: list[str] = Field(default_factory=list)
    recorded_at: datetime = Field(default_factory=_now)
