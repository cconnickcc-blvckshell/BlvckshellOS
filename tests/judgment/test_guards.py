"""Tests for harm and safe-divergence guards."""

from harness.schemas.judgment import JudgmentEntry
from judgment.guards.harm_aware import apply_harm_guard
from judgment.guards.safe_divergence import apply_safe_divergence
from judgment.guards.tension import DivergenceTension
from judgment.outcome import JudgmentOutcome
from judgment.profile import JudgmentProfile
from judgment.traces import EvidenceBundle


def test_harm_guard_blocks_capital_hold_to_proceed() -> None:
    profile = JudgmentProfile(domain="capital", harm_guard_enabled=True)
    evidence = EvidenceBundle(summary="ok", evidence_positive=True)

    outcome, reason = apply_harm_guard(
        profile,
        prior_outcome=JudgmentOutcome.HOLD,
        proposed=JudgmentOutcome.PROCEED,
        evidence=evidence,
    )

    assert outcome == JudgmentOutcome.HOLD
    assert reason == "harm_guard:block_hold_to_proceed"


def test_harm_guard_blocks_proceed_without_positive_evidence() -> None:
    profile = JudgmentProfile(domain="capital", harm_guard_enabled=True)
    evidence = EvidenceBundle(summary="no-go", evidence_positive=False)

    outcome, reason = apply_harm_guard(
        profile,
        prior_outcome=None,
        proposed=JudgmentOutcome.PROCEED,
        evidence=evidence,
    )

    assert outcome == JudgmentOutcome.HOLD
    assert reason == "harm_guard:case_evidence_not_positive"


def test_harm_guard_blocks_negative_roi() -> None:
    profile = JudgmentProfile(domain="capital", harm_guard_enabled=True, min_roi_signal=0.0)
    evidence = EvidenceBundle(summary="deploy", evidence_positive=True, expected_roi=-0.05)

    outcome, reason = apply_harm_guard(
        profile,
        prior_outcome=None,
        proposed=JudgmentOutcome.PROCEED,
        evidence=evidence,
    )

    assert outcome == JudgmentOutcome.HOLD
    assert reason == "harm_guard:expected_roi_not_positive"


def test_harm_guard_blocks_risk_above_cap() -> None:
    profile = JudgmentProfile(domain="capital", harm_guard_enabled=True, risk_cap=0.3)
    evidence = EvidenceBundle(summary="deploy", evidence_positive=True, risk_score=0.45)

    outcome, reason = apply_harm_guard(
        profile,
        prior_outcome=None,
        proposed=JudgmentOutcome.PROCEED,
        evidence=evidence,
    )

    assert outcome == JudgmentOutcome.HOLD
    assert reason == "harm_guard:recursive_risk_above_cap"


def test_harm_guard_blocks_similar_past_poor_outcomes() -> None:
    profile = JudgmentProfile(domain="capital", harm_guard_enabled=True)
    evidence = EvidenceBundle(summary="trading deployment", evidence_positive=True)
    recent = [
        JudgmentEntry(
            brain_id="capital",
            context_id="c1",
            belief="Prior trading deployment failed",
            confidence=0.8,
            changelog=[
                {
                    "action": "outcome_recorded",
                    "details": {"outcome_quality": -0.5},
                }
            ],
        )
    ]

    outcome, reason = apply_harm_guard(
        profile,
        prior_outcome=None,
        proposed=JudgmentOutcome.PROCEED,
        evidence=evidence,
        recent_judgments=recent,
        belief_hint="trading deployment capital",
    )

    assert outcome == JudgmentOutcome.HOLD
    assert reason == "harm_guard:similar_past_outcome_poor"


def test_harm_guard_inactive_for_non_capital() -> None:
    profile = JudgmentProfile(domain="venture", harm_guard_enabled=True)
    evidence = EvidenceBundle(summary="no-go", evidence_positive=False)

    outcome, reason = apply_harm_guard(
        profile,
        prior_outcome=JudgmentOutcome.HOLD,
        proposed=JudgmentOutcome.PROCEED,
        evidence=evidence,
    )

    assert outcome == JudgmentOutcome.PROCEED
    assert reason is None


def test_safe_divergence_allows_proceed_to_staged_borderline() -> None:
    profile = JudgmentProfile()
    evidence = EvidenceBundle(
        summary="marginal",
        evidence_positive=True,
        confidence=0.72,
        risk_score=0.28,
        expected_roi=0.02,
    )
    outcome, reason, tension = apply_safe_divergence(
        profile,
        baseline=JudgmentOutcome.PROCEED,
        candidate=JudgmentOutcome.STAGED_PROCEED,
        evidence=evidence,
        confidence=0.72,
    )
    assert outcome == JudgmentOutcome.STAGED_PROCEED
    assert reason is None
    assert tension in (DivergenceTension.BORDERLINE, DivergenceTension.WEAK_PROCEED)


def test_safe_divergence_blocks_hold_to_proceed() -> None:
    profile = JudgmentProfile()
    outcome, reason, _ = apply_safe_divergence(
        profile,
        baseline=JudgmentOutcome.HOLD,
        candidate=JudgmentOutcome.PROCEED,
        prior_outcome=JudgmentOutcome.HOLD,
    )
    assert outcome == JudgmentOutcome.HOLD
    assert reason == "safe_divergence:block_hold_to_proceed"


def test_safe_divergence_contested_to_request_more_evidence() -> None:
    profile = JudgmentProfile()
    evidence = EvidenceBundle(summary="conflict", evidence_positive=False)
    outcome, _, tension = apply_safe_divergence(
        profile,
        baseline=JudgmentOutcome.PROCEED,
        candidate=JudgmentOutcome.PROCEED,
        evidence=evidence,
        confidence=0.5,
    )
    assert outcome == JudgmentOutcome.REQUEST_MORE_EVIDENCE
    assert tension == DivergenceTension.CONTESTED
