"""Tests for evidence classification."""

from harness.core.agent_loop import AgentLoopResult
from judgment.evidence import assess_evidence
from judgment.outcome import JudgmentOutcome


def test_assess_evidence_parses_no_go_as_hold() -> None:
    outcome = AgentLoopResult(final_text="Recommendation: NO-GO due to market risk.")
    bundle = assess_evidence(outcome, domain="venture")
    assert bundle.provisional_outcome == JudgmentOutcome.HOLD
    assert bundle.evidence_positive is False


def test_assess_evidence_parses_conditional_as_staged() -> None:
    outcome = AgentLoopResult(final_text="CONDITIONAL proceed with a pilot phase first.")
    bundle = assess_evidence(outcome, domain="venture")
    assert bundle.provisional_outcome == JudgmentOutcome.STAGED_PROCEED


def test_assess_evidence_parses_evidence_gap() -> None:
    outcome = AgentLoopResult(final_text="We need more data before deciding.")
    bundle = assess_evidence(outcome, domain="venture")
    assert bundle.provisional_outcome == JudgmentOutcome.REQUEST_MORE_EVIDENCE
