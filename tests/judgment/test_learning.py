"""Unit tests for post-outcome belief update (J10)."""

from harness.schemas.judgment import JudgmentEntry, OutcomeRecord
from judgment.stages.learning import apply_belief_update


def test_positive_outcome_increases_confidence() -> None:
    entry = JudgmentEntry(
        brain_id="venture", context_id="c1", belief="GO on product", confidence=0.7
    )
    updated, trace = apply_belief_update(
        entry, OutcomeRecord(actual_outcome="Success", outcome_quality=0.85)
    )
    assert updated.confidence > 0.7
    assert trace.confidence_after == updated.confidence
    assert len(updated.evidence) >= 1


def test_negative_outcome_decreases_and_flags() -> None:
    entry = JudgmentEntry(
        brain_id="venture", context_id="c1", belief="GO on product", confidence=0.7
    )
    updated, trace = apply_belief_update(
        entry, OutcomeRecord(actual_outcome="Failed", outcome_quality=-0.5)
    )
    assert updated.confidence < 0.7
    assert trace.flagged_for_review is True
