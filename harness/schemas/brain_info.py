"""Brain registration and context schemas.

:class:`BrainInfo` is the advertisement a brain publishes to the registry.
:class:`BrainContext` is the working context a brain loads from shared memory
before it thinks.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from harness.schemas.judgment import JudgmentEntry


def _now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


class BrainState(str, Enum):
    """Live state of a brain, mirrored by the status orbs in the UI."""

    IDLE = "IDLE"
    THINKING = "THINKING"
    EXECUTING = "EXECUTING"
    ERROR = "ERROR"
    OFFLINE = "OFFLINE"


class BrainInfo(BaseModel):
    """A brain's self-description as advertised to the registry.

    Attributes:
        brain_id: Unique identifier.
        name: Human readable name.
        description: What the brain does.
        capabilities: Task capabilities the brain can handle.
        model: Which LLM the brain uses.
        tools: Names of tools the brain has access to.
        state: Current live state.
        last_heartbeat: When the brain last reported healthy.
        registered_at: When the brain first registered.
    """

    brain_id: str
    name: str
    description: str
    capabilities: list[str] = Field(default_factory=list)
    model: str = "unknown"
    tools: list[str] = Field(default_factory=list)
    state: BrainState = BrainState.IDLE
    last_heartbeat: datetime = Field(default_factory=_now)
    registered_at: datetime = Field(default_factory=_now)

    def handles(self, capability: str) -> bool:
        """Return whether this brain advertises the given capability."""
        return capability in self.capabilities


class BrainContext(BaseModel):
    """Working context a brain loads from shared memory before thinking.

    Attributes:
        context_id: The pipeline run this context belongs to.
        brain_id: The brain the context was loaded for.
        working_memory: Short-lived pipeline state from Redis.
        recent_judgments: Recent relevant Judgment Ledger entries.
        doctrine: Validated beliefs relevant to the task.
        history: Prior messages/results in this pipeline run.
    """

    context_id: str
    brain_id: str
    working_memory: dict[str, Any] = Field(default_factory=dict)
    recent_judgments: list[JudgmentEntry] = Field(default_factory=list)
    doctrine: list[JudgmentEntry] = Field(default_factory=list)
    history: list[dict[str, Any]] = Field(default_factory=list)
