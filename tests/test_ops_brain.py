"""Tests for the Ops Brain — financial/account actions are flagged, never executed."""

from __future__ import annotations

from harness.core.harness import Harness
from harness.schemas.message import HarnessMessage, MessageType
from harness.schemas.result import Result, ResultStatus
from harness.schemas.task import Task
from brains.blvckbot.ops import (
    OpsBrain,
    _flag_financial_action,
    _package_deliverable,
    _summarize_run_status,
)


async def test_summarize_run_status_counts_tasks() -> None:
    out = await _summarize_run_status(
        {"task_statuses": {"t1": "COMPLETED", "t2": "COMPLETED", "t3": "FAILED"}}
    )
    assert out["summary"] == "2/3 tasks completed"
    assert out["counts"]["COMPLETED"] == 2


async def test_package_deliverable_requires_content() -> None:
    out = await _package_deliverable({})
    assert "error" in out


async def test_package_deliverable_marks_ready() -> None:
    out = await _package_deliverable({"files": ["logo.svg"], "notes": "final version"})
    assert out["ready_for_review"] is True


async def test_flag_financial_action_never_executes() -> None:
    out = await _flag_financial_action(
        {"action": "withdraw earnings", "reason": "month-end payout", "amount": 1200}
    )
    assert out["executed"] is False
    assert out["requires_human_confirmation"] is True


async def test_flag_financial_action_requires_action() -> None:
    out = await _flag_financial_action({})
    assert "error" in out


async def test_ops_brain_registered(harness: Harness) -> None:
    brains = await harness.registry.list_all()
    assert any(b.brain_id == "ops" for b in brains)


async def test_ops_output_always_needs_operator_confirmation(harness: Harness) -> None:
    """Even a confident PROCEED status report must surface as NEEDS_OPERATOR."""
    brain = harness.get_worker("ops")
    assert isinstance(brain, OpsBrain)

    task = Task(
        run_id="test-run",
        objective_id="test-objective",
        capability="financial_action_flagging",
        objective="Flag the month-end payout for review.",
        inputs={},
    )
    message = HarnessMessage(
        source="test",
        destination=brain.brain_id,
        message_type=MessageType.TASK,
        payload=task.model_dump(mode="json"),
        context_id="test-run",
    )

    reply = await brain.handle_task(message)
    result = Result.model_validate(reply.payload)

    assert result.status == ResultStatus.NEEDS_OPERATOR
    assert result.judgment_outcome.value == "REQUEST_MORE_EVIDENCE"
