"""Tests for judgment lifecycle wiring."""

from __future__ import annotations

from harness.core.agent_loop import AgentLoopResult
from harness.schemas.brain_info import BrainContext
from harness.schemas.judgment import JudgmentEntry
from harness.schemas.task import Task
from judgment.lifecycle import JudgmentLifecycle, build_ledger_entry
from judgment.outcome import JudgmentOutcome
from judgment.profile import JudgmentProfile
from judgment.traces import JudgmentStage


async def test_lifecycle_emits_all_nine_stages() -> None:
    lifecycle = JudgmentLifecycle()
    task = Task(
        run_id="run-1",
        objective_id="obj-1",
        capability="idea_validation",
        objective="Validate the trading AI idea",
    )
    context = BrainContext(context_id="run-1", brain_id="venture")

    async def gather_evidence() -> AgentLoopResult:
        return AgentLoopResult(final_text="GO — strong market fit and feasible build.")

    result = await lifecycle.run(
        brain_id="venture",
        context_id="run-1",
        task=task,
        context=context,
        profile=JudgmentProfile(domain="venture", exploration_enabled=False),
        gather_evidence=gather_evidence,
        observer=None,
    )

    stage_names = [s.stage for s in result.stages]
    assert len(stage_names) == 9
    assert stage_names[0] == JudgmentStage.OBSERVATION
    assert stage_names[-1] == JudgmentStage.LEARNING
    assert result.outcome == JudgmentOutcome.PROCEED


async def test_lifecycle_capital_harm_guard_blocks_proceed() -> None:
    lifecycle = JudgmentLifecycle()
    task = Task(
        run_id="run-1",
        objective_id="obj-1",
        capability="capital_flagging",
        objective="Allocate $2M to trading AI",
    )
    context = BrainContext(
        context_id="run-1",
        brain_id="capital",
        recent_judgments=[
            JudgmentEntry(
                brain_id="capital",
                context_id="run-1",
                belief="Prior hold on capital deployment",
                confidence=0.8,
                assumptions=["judgment_outcome:HOLD"],
            )
        ],
    )

    async def gather_evidence() -> AgentLoopResult:
        return AgentLoopResult(final_text="PROCEED — deploy full capital immediately.")

    result = await lifecycle.run(
        brain_id="capital",
        context_id="run-1",
        task=task,
        context=context,
        profile=JudgmentProfile(
            domain="capital", harm_guard_enabled=True, exploration_enabled=False
        ),
        gather_evidence=gather_evidence,
        observer=None,
    )

    assert result.outcome == JudgmentOutcome.HOLD
    assert any(
        reason in result.guard_blocks
        for reason in (
            "harm_guard:block_hold_to_proceed",
            "safe_divergence:block_hold_to_proceed",
        )
    )


async def test_lifecycle_decision_consumes_evidence_bundle() -> None:
    lifecycle = JudgmentLifecycle()
    task = Task(
        run_id="run-1",
        objective_id="obj-1",
        capability="idea_validation",
        objective="Validate the trading AI idea",
    )
    context = BrainContext(context_id="run-1", brain_id="venture")

    async def gather_evidence() -> AgentLoopResult:
        return AgentLoopResult(final_text="GO — strong market fit and feasible build.")

    result = await lifecycle.run(
        brain_id="venture",
        context_id="run-1",
        task=task,
        context=context,
        profile=JudgmentProfile(domain="venture"),
        gather_evidence=gather_evidence,
        observer=None,
    )

    from judgment.traces import get_stage_trace

    decision_trace = get_stage_trace(result.stages, "DECISION")
    assert decision_trace is not None
    assert "evidence_bundle" in decision_trace.consumed_signals


def test_build_ledger_entry_records_outcome_in_changelog() -> None:
    from judgment.traces import LifecycleResult

    cycle = LifecycleResult(
        outcome=JudgmentOutcome.STAGED_PROCEED,
        belief="Pilot first",
        confidence=0.75,
    )
    entry = build_ledger_entry(brain_id="venture", context_id="run-1", lifecycle=cycle)
    assert any(a.startswith("judgment_outcome:") for a in entry.assumptions)
    assert entry.changelog[-1]["action"] == "judgment_lifecycle"
