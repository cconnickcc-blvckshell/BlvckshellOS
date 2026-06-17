"""Task payload schema — the unit of work routed to a brain."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Lifecycle states of a task as it moves through the harness."""

    PENDING = "pending"
    ROUTED = "routed"
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskPayload(BaseModel):
    """Self-contained description of work for a single brain.

    A ``TaskPayload`` is what rides inside a ``TASK`` message's ``payload``.
    It is deliberately brain-agnostic: any brain advertising a matching
    capability can pick it up.

    Attributes:
        task_id: Stable identifier for this task within a pipeline.
        capability: The capability required to execute this task.
        objective: Natural-language statement of what must be accomplished.
        inputs: Structured inputs the brain needs.
        constraints: Hard limits the brain must respect.
        depends_on: ``task_id`` values that must finish before this one runs.
        status: Current lifecycle status.
        assigned_brain: ``brain_id`` the task was routed to, once known.
    """

    task_id: str
    capability: str
    objective: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    constraints: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    assigned_brain: str | None = None
