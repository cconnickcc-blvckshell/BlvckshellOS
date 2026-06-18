"""Harm-aware guard — authoritative override before outcome promotion."""

from __future__ import annotations

from harness.schemas.judgment import JudgmentEntry

from judgment.outcome import JudgmentOutcome
from judgment.profile import JudgmentProfile
from judgment.traces import EvidenceBundle

_CAPITAL_DOMAINS = frozenset({"capital"})


def _outcome_quality(entry: JudgmentEntry) -> float | None:
    for change in reversed(entry.changelog):
        if change.get("action") == "outcome_recorded":
            quality = (change.get("details") or {}).get("outcome_quality")
            if quality is not None:
                return float(quality)
    return None


def _similar_past_quality_poor(
    recent: list[JudgmentEntry],
    *,
    belief_hint: str,
    threshold: float = -0.3,
) -> bool:
    """True when similar past decisions had poor outcome quality."""
    keywords = {w.lower() for w in belief_hint.split() if len(w) > 4}
    if not keywords:
        return False
    for entry in recent:
        quality = _outcome_quality(entry)
        if quality is None or quality > threshold:
            continue
        belief_tokens = set(entry.belief.lower().split())
        if keywords & belief_tokens:
            return True
    return False


def apply_harm_guard(
    profile: JudgmentProfile,
    *,
    prior_outcome: JudgmentOutcome | None,
    proposed: JudgmentOutcome,
    evidence: EvidenceBundle,
    recent_judgments: list[JudgmentEntry] | None = None,
    belief_hint: str = "",
) -> tuple[JudgmentOutcome, str | None]:
    """Block unsafe outcome transitions. Returns (outcome, block_reason)."""
    if not profile.harm_guard_enabled:
        return proposed, None

    if profile.domain not in _CAPITAL_DOMAINS:
        return proposed, None

    if prior_outcome == JudgmentOutcome.HOLD and proposed == JudgmentOutcome.PROCEED:
        return JudgmentOutcome.HOLD, "harm_guard:block_hold_to_proceed"

    if proposed != JudgmentOutcome.PROCEED:
        return proposed, None

    if not evidence.evidence_positive:
        return JudgmentOutcome.HOLD, "harm_guard:case_evidence_not_positive"

    if evidence.expected_roi is not None and evidence.expected_roi <= profile.min_roi_signal:
        return JudgmentOutcome.HOLD, "harm_guard:expected_roi_not_positive"

    if evidence.risk_score is not None and evidence.risk_score > profile.risk_cap:
        return JudgmentOutcome.HOLD, "harm_guard:recursive_risk_above_cap"

    if recent_judgments and _similar_past_quality_poor(
        recent_judgments,
        belief_hint=belief_hint or evidence.summary,
    ):
        return JudgmentOutcome.HOLD, "harm_guard:similar_past_outcome_poor"

    return proposed, None
