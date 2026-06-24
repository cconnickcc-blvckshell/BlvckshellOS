"""Tests for the Proposal Brain — drafting is always gated to human approval."""

from __future__ import annotations

from harness.core.harness import Harness
from harness.schemas.message import HarnessMessage, MessageType
from harness.schemas.result import Result, ResultStatus
from harness.schemas.task import Task
from brains.blvckbot.proposal import ProposalBrain, _estimate_price_band


async def test_estimate_price_band_from_client_budget() -> None:
    out = await _estimate_price_band({"client_budget": 1000})
    assert out["target"] == 1000.0
    assert out["low"] < 1000.0 < out["high"]


async def test_estimate_price_band_from_hours_and_rate() -> None:
    out = await _estimate_price_band({"estimated_hours": 10, "hourly_rate": 50})
    assert out["target"] == 500.0


async def test_estimate_price_band_requires_input() -> None:
    out = await _estimate_price_band({})
    assert "error" in out


async def test_proposal_brain_registered(harness: Harness) -> None:
    brains = await harness.registry.list_all()
    assert any(b.brain_id == "proposal" for b in brains)


async def test_proposal_draft_always_needs_operator_approval(harness: Harness) -> None:
    """Even a confident PROCEED draft must surface as NEEDS_OPERATOR — never auto-sent."""
    brain = harness.get_worker("proposal")
    assert isinstance(brain, ProposalBrain)

    task = Task(
        run_id="test-run",
        objective_id="test-objective",
        capability="proposal_drafting",
        objective="Draft a proposal for a $500 logo design job for a coffee shop.",
        inputs={"client_budget": 500},
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
