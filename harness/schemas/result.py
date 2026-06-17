"""Result schema.

A :class:`Result` is the structured payload carried inside a ``RESULT``
:class:`~harness.schemas.message.HarnessMessage`. A brain returns one of these
when it finishes (successfully or not) a task.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ResultStatus(str, Enum):
    """Whether a task succeeded, failed, or needs the operator."""

    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    NEEDS_OPERATOR = "NEEDS_OPERATOR"


class Result(BaseModel):
    """The outcome of a brain executing a task.

    Attributes:
        task_id: The id of the task this result answers.
        brain_id: The brain that produced the result.
        status: Whether the task succeeded, failed, or is blocked.
        output: The primary structured output of the work.
        summary: A short human-readable summary of the outcome.
        error: Error detail when ``status`` is ``FAILURE``.
        judgment_ids: IDs of Judgment Ledger entries created during the task.
        metrics: Timing, tokens, cost, tool-call counts, etc.
    """

    task_id: str
    brain_id: str
    status: ResultStatus
    output: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""
    error: str | None = None
    judgment_ids: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)

    @property
    def succeeded(self) -> bool:
        """Whether the task completed successfully."""
        return self.status == ResultStatus.SUCCESS
