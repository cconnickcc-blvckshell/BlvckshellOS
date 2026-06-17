"""The execution hierarchy: Objective -> Run -> Task -> AgentCall.

The flat ``context_id`` of v1 is replaced by an explicit ancestry:

- :class:`Objective` — the operator's intent. Stable; never changes.
- :class:`Run` — one execution attempt of an objective.
- :class:`~harness.schemas.task.Task` — one unit of work within a run.
- :class:`AgentCall` — one sub-agent invocation spawned by a brain.

Every component that receives a message can therefore reconstruct exactly where
it sits in the tree, and a brain spawning a sub-agent knows its parent task and
run rather than just a flat id.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from harness.schemas.result import Result
from harness.schemas.task import Task, TaskStatus


def _now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


def _new_id() -> str:
    """Return a fresh UUID4 string."""
    return str(uuid.uuid4())


class RunStatus(str, Enum):
    """Lifecycle status of a single execution run."""

    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    NEEDS_OPERATOR = "NEEDS_OPERATOR"


class Objective(BaseModel):
    """The operator's intent — the top of the hierarchy.

    Attributes:
        objective_id: Stable identifier for the intent; never changes.
        statement: The raw idea/text the operator submitted.
        created_at: When the objective was captured (UTC).
    """

    objective_id: str = Field(default_factory=_new_id)
    statement: str
    created_at: datetime = Field(default_factory=_now)


class Run(BaseModel):
    """One execution attempt of an :class:`Objective`.

    Attributes:
        run_id: Identifier for this execution attempt.
        objective_id: The parent objective.
        status: Current run status.
        started_at: When the run began (UTC).
        completed_at: When the run finished, if it has.
        output: The synthesized final answer.
        tasks: The tasks the orchestrator produced for this run.
        results: The results returned by brains.
    """

    run_id: str = Field(default_factory=_new_id)
    objective_id: str
    status: RunStatus = RunStatus.RUNNING
    started_at: datetime = Field(default_factory=_now)
    completed_at: datetime | None = None
    output: str = ""
    tasks: list[Task] = Field(default_factory=list)
    results: list[Result] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the run."""
        return self.model_dump(mode="json")


class AgentCall(BaseModel):
    """One sub-agent invocation spawned by a brain.

    Attributes:
        agent_call_id: Identifier for this sub-agent invocation.
        task_id: The parent task that spawned the sub-agent.
        run_id: The grandparent run.
        objective_id: The great-grandparent objective.
        spawned_by: The ``brain_id`` that spawned this sub-agent.
        capability: The capability requested of the sub-agent.
        objective: The instruction given to the sub-agent.
        inputs: Structured inputs passed to the sub-agent.
        result: The sub-agent's result summary, once returned.
        error: Error detail if the sub-agent failed.
        status: Lifecycle status of the sub-agent call.
    """

    agent_call_id: str = Field(default_factory=_new_id)
    task_id: str
    run_id: str
    objective_id: str
    spawned_by: str
    capability: str
    objective: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    result: str | None = None
    error: str | None = None
    status: TaskStatus = TaskStatus.PENDING
