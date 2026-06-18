"""Foundation — post-outcome Bayesian belief update (J10)."""

from __future__ import annotations

from dataclasses import dataclass

from harness.schemas.judgment import JudgmentEntry, OutcomeRecord

CONFIDENCE_CAP = 0.95
CONFIDENCE_FLOOR = 0.05
POSITIVE_QUALITY_THRESHOLD = 0.7
NEGATIVE_QUALITY_THRESHOLD = -0.3


@dataclass(slots=True)
class BeliefUpdateTrace:
    """Trace of a belief confidence update after outcome."""

    judgment_id: str
    confidence_before: float
    confidence_after: float
    flagged_for_review: bool
    signals_consumed: list[str]


def apply_belief_update(
    entry: JudgmentEntry,
    outcome_data: OutcomeRecord,
) -> tuple[JudgmentEntry, BeliefUpdateTrace]:
    """Update ledger entry confidence from recorded outcome quality."""
    before = entry.confidence
    after = before
    flagged = False
    consumed = ["outcome_record.outcome_quality"]

    if outcome_data.outcome_quality >= POSITIVE_QUALITY_THRESHOLD:
        after = min(CONFIDENCE_CAP, before + 0.05)
        evidence_note = f"outcome:{outcome_data.actual_outcome[:80]}"
        if evidence_note not in entry.evidence:
            entry.evidence.append(evidence_note)
        consumed.append("outcome.positive_reinforcement")
    elif outcome_data.outcome_quality <= NEGATIVE_QUALITY_THRESHOLD:
        after = max(CONFIDENCE_FLOOR, before - 0.1)
        flagged = True
        entry.record_change(
            "belief_flagged_for_review",
            {"outcome_quality": outcome_data.outcome_quality},
        )
        consumed.append("outcome.negative_penalty")

    entry.confidence = after
    entry.record_change(
        "belief_updated",
        {
            "confidence_before": before,
            "confidence_after": after,
            "outcome_quality": outcome_data.outcome_quality,
        },
    )

    trace = BeliefUpdateTrace(
        judgment_id=entry.id,
        confidence_before=before,
        confidence_after=after,
        flagged_for_review=flagged,
        signals_consumed=consumed,
    )
    return entry, trace
