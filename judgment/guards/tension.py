"""Decision tension classification for safe divergence."""

from __future__ import annotations

from enum import Enum

from judgment.traces import EvidenceBundle


class DivergenceTension(str, Enum):
    """Tension class before safe-divergence guard fires."""

    STRONG_PROCEED = "strong_proceed"
    BORDERLINE = "borderline"
    WEAK_PROCEED = "weak_proceed"
    CONTESTED = "contested"


def classify_tension(
    evidence: EvidenceBundle,
    *,
    confidence: float,
) -> DivergenceTension:
    """Classify decision tension from evidence and confidence signals."""
    if not evidence.evidence_positive:
        return DivergenceTension.CONTESTED

    risk = evidence.risk_score or 0.0
    roi = evidence.expected_roi

    if confidence >= 0.85 and risk < 0.25 and (roi is None or roi > 0.05):
        return DivergenceTension.STRONG_PROCEED

    if confidence < 0.55 or (roi is not None and roi < 0.0):
        return DivergenceTension.CONTESTED

    if confidence < 0.7 or risk >= 0.4 or (roi is not None and 0.0 <= roi <= 0.05):
        return DivergenceTension.WEAK_PROCEED

    if confidence < 0.8 or risk >= 0.25:
        return DivergenceTension.BORDERLINE

    return DivergenceTension.STRONG_PROCEED
