"""Schemas describing brains: registration metadata and loaded context."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


class BrainStatus(str, Enum):
    """Health/activity state of a registered brain.

    These values map directly to the frontend brain status orbs.
    """

    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    ERROR = "error"
    OFFLINE = "offline"


class BrainInfo(BaseModel):
    """Advertised identity and capabilities of a brain in the registry.

    Attributes:
        brain_id: Unique identifier.
        name: Human-readable name.
        description: What the brain does.
        capabilities: Task capabilities the brain can handle.
        model: The LLM the brain uses.
        status: Current activity/health status.
        registered_at: When the brain first registered.
        last_heartbeat: Most recent heartbeat timestamp.
        current_task_id: Task currently being processed, if any.
        metadata: Free-form extra advertisement data.
    """

    brain_id: str
    name: str
    description: str
    capabilities: list[str] = Field(default_factory=list)
    model: str
    status: BrainStatus = BrainStatus.IDLE
    registered_at: datetime = Field(default_factory=_utcnow)
    last_heartbeat: datetime = Field(default_factory=_utcnow)
    current_task_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BrainContext(BaseModel):
    """The working context a brain loads before it thinks.

    Aggregates the three memory tiers into one object the agent loop can hand
    to the LLM.

    Attributes:
        context_id: The pipeline run this context belongs to.
        brain_id: The brain the context was assembled for.
        working: Volatile pipeline state (Redis / working memory).
        episodic: Relevant completed runs and history.
        doctrine: Validated beliefs relevant to the task.
        recent_judgments: Recent ledger entries for this context.
    """

    context_id: str
    brain_id: str
    working: dict[str, Any] = Field(default_factory=dict)
    episodic: list[dict[str, Any]] = Field(default_factory=list)
    doctrine: list[dict[str, Any]] = Field(default_factory=list)
    recent_judgments: list[dict[str, Any]] = Field(default_factory=list)
