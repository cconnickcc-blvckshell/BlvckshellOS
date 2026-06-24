"""Tests for the Build Brain — briefs/reviews are always gated to human review."""

from __future__ import annotations

from harness.core.harness import Harness
from harness.schemas.message import HarnessMessage, MessageType
from harness.schemas.result import Result, ResultStatus
from harness.schemas.task import Task
from brains.blvckbot.build import BuildBrain, _estimate_build_effort, _review_against_checklist


async def test_estimate_build_effort_sums_tasks() -> None:
    out = await _estimate_build_effort({"tasks": {"setup": 2, "implementation": 6, "tests": 2}})
    assert out["total_hours"] == 10.0


async def test_estimate_build_effort_handles_empty() -> None:
    out = await _estimate_build_effort({"tasks": {}})
    assert out["total_hours"] == 0.0


async def test_review_against_checklist_tallies_pass_fail() -> None:
    out = await _review_against_checklist(
        {
            "items": [
                {"requirement": "Logo delivered in SVG", "passed": True},
                {"requirement": "Color variants included", "passed": False},
            ]
        }
    )
    assert out["passed_count"] == 1
    assert out["total_count"] == 2
    assert out["all_passed"] is False


async def test_build_brain_registered(harness: Harness) -> None:
    brains = await harness.registry.list_all()
    assert any(b.brain_id == "build" for b in brains)


async def test_build_brief_always_needs_operator_review(harness: Harness) -> None:
    """Even a confident PROCEED brief must surface as NEEDS_OPERATOR before delivery."""
    brain = harness.get_worker("build")
    assert isinstance(brain, BuildBrain)

    task = Task(
        run_id="test-run",
        objective_id="test-objective",
        capability="build_brief",
        objective="Scope a build brief for a 5-page marketing site.",
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
