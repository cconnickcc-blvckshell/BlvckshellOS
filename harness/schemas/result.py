"""Result payload schema — what a brain returns after executing a task."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ResultStatus(str, Enum):
    """Terminal outcome of a brain executing a task."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    BLOCKED = "blocked"


class ResultPayload(BaseModel):
    """Structured output a brain emits back onto the message bus.

    A ``ResultPayload`` rides inside a ``RESULT`` message's ``payload``.

    Attributes:
        task_id: The task this result answers.
        brain_id: The brain that produced it.
        status: Terminal outcome.
        summary: Human-readable synthesis of the work.
        output: Structured machine-readable output.
        artifacts: References to produced artifacts (files, urls, ids).
        judgment_ids: Judgment Ledger entries created while doing the work.
        error: Failure detail, present only when status is ``failed``.
        usage: Token/cost/latency accounting for the work.
    """

    task_id: str
    brain_id: str
    status: ResultStatus
    summary: str
    output: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[str] = Field(default_factory=list)
    judgment_ids: list[str] = Field(default_factory=list)
    error: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)
