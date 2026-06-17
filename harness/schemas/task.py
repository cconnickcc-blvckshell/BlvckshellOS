"""Task definition schema.

A :class:`Task` is the structured payload carried inside a ``TASK``
:class:`~harness.schemas.message.HarnessMessage`. CKOS decomposes an operator's
idea into one or more tasks and routes each to a capable brain.
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Lifecycle states of a task."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class Task(BaseModel):
    """A discrete, executable unit of work assigned to a brain.

    Attributes:
        id: Unique identifier for the task.
        capability: The capability required to handle the task. The registry
            uses this to route to a brain advertising the capability.
        objective: Human-readable description of what to accomplish.
        inputs: Structured inputs the brain needs to do the work.
        depends_on: IDs of tasks that must complete before this one may run.
        priority: ``1``-``5`` where ``5`` is highest.
        status: Current lifecycle status.
        assigned_brain: The ``brain_id`` chosen to handle this task, if routed.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    capability: str
    objective: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    priority: int = Field(default=3, ge=1, le=5)
    status: TaskStatus = TaskStatus.PENDING
    assigned_brain: str | None = None

    @property
    def is_independent(self) -> bool:
        """Whether this task has no unmet dependencies and can run in parallel."""
        return not self.depends_on
