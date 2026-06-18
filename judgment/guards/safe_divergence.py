"""Safe divergence guard — productive de-risking only."""

from __future__ import annotations

from judgment.guards.tension import DivergenceTension, classify_tension
from judgment.outcome import JudgmentOutcome
from judgment.profile import JudgmentProfile
from judgment.traces import EvidenceBundle


def apply_safe_divergence(
    profile: JudgmentProfile,
    *,
    baseline: JudgmentOutcome,
    candidate: JudgmentOutcome,
    evidence: EvidenceBundle | None = None,
    confidence: float = 0.7,
    prior_outcome: JudgmentOutcome | None = None,
) -> tuple[JudgmentOutcome, str | None, DivergenceTension | None]:
    """Allow only safe beneficial divergence. Returns (outcome, block_reason, tension)."""
    tension: DivergenceTension | None = None
    if evidence is not None:
        tension = classify_tension(evidence, confidence=confidence)

    if not profile.safe_divergence_enabled:
        return candidate, None, tension

    # Forbidden transitions — return baseline, log block
    if prior_outcome == JudgmentOutcome.HOLD and candidate == JudgmentOutcome.PROCEED:
        return JudgmentOutcome.HOLD, "safe_divergence:block_hold_to_proceed", tension

    if prior_outcome == JudgmentOutcome.HOLD and candidate == JudgmentOutcome.STAGED_PROCEED:
        return JudgmentOutcome.HOLD, "safe_divergence:block_hold_to_staged", tension

    if baseline == JudgmentOutcome.STAGED_PROCEED and candidate == JudgmentOutcome.PROCEED:
        return baseline, "safe_divergence:block_staged_to_proceed", tension

    if tension == DivergenceTension.CONTESTED:
        return JudgmentOutcome.REQUEST_MORE_EVIDENCE, None, tension

    if tension == DivergenceTension.STRONG_PROCEED and candidate == JudgmentOutcome.STAGED_PROCEED:
        return JudgmentOutcome.PROCEED, "safe_divergence:strong_proceed_no_derisk", tension

    # Allowlisted: PROCEED → STAGED_PROCEED for borderline / weak
    if baseline == JudgmentOutcome.PROCEED and candidate == JudgmentOutcome.STAGED_PROCEED:
        if tension in (DivergenceTension.BORDERLINE, DivergenceTension.WEAK_PROCEED):
            return JudgmentOutcome.STAGED_PROCEED, None, tension
        if tension == DivergenceTension.STRONG_PROCEED:
            return JudgmentOutcome.PROCEED, "safe_divergence:strong_proceed_no_derisk", tension

    # Allowlisted: STAGED_PROCEED → REQUEST_MORE_EVIDENCE
    if (
        baseline == JudgmentOutcome.STAGED_PROCEED
        and candidate == JudgmentOutcome.REQUEST_MORE_EVIDENCE
    ):
        return JudgmentOutcome.REQUEST_MORE_EVIDENCE, None, tension

    if candidate in (JudgmentOutcome.HOLD, JudgmentOutcome.REQUEST_MORE_EVIDENCE):
        return candidate, None, tension

    if baseline != candidate:
        return baseline, f"safe_divergence:block_{baseline.value}_to_{candidate.value}", tension

    return candidate, None, tension
