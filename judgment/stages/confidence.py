"""Foundation — pre-decision confidence adjustment (J9)."""

from __future__ import annotations

from dataclasses import dataclass, field

from harness.schemas.brain_info import BrainContext
from harness.schemas.judgment import JudgmentEntry

from judgment.profile import JudgmentProfile


@dataclass(slots=True)
class ConfidenceAdjustTrace:
    """Trace output from the Confidence stage."""

    base_confidence: float
    doctrine_adjustment: float
    outcome_adjustment: float
    final_confidence: float
    signals_consumed: list[str] = field(default_factory=list)


def _outcome_quality(entry: JudgmentEntry) -> float | None:
    for change in reversed(entry.changelog):
        if change.get("action") == "outcome_recorded":
            quality = (change.get("details") or {}).get("outcome_quality")
            if quality is not None:
                return float(quality)
    return None


def adjust_confidence(
    profile: JudgmentProfile,
    context: BrainContext,
    *,
    base_confidence: float = 0.7,
) -> ConfidenceAdjustTrace:
    """Adjust confidence from doctrine and recent ledger outcomes."""
    consumed: list[str] = []
    doctrine_adj = 0.0
    outcome_adj = 0.0

    matching_doctrine = [
        d
        for d in context.doctrine
        if d.confidence >= 0.7 and profile.domain in (d.brain_id, "general", profile.domain)
    ]
    if matching_doctrine:
        consumed.append("doctrine.high_confidence")
        high = [d for d in matching_doctrine if d.confidence >= 0.85]
        doctrine_adj = 0.1 if high else 0.05

    recent = context.recent_judgments[: profile.recall_depth]
    qualities = [q for q in (_outcome_quality(e) for e in recent) if q is not None]
    if qualities:
        consumed.append("ledger.recent_outcomes")
        avg = sum(qualities) / len(qualities)
        if avg < 0.3:
            outcome_adj = -0.15 if avg < 0.1 else -0.05
        elif avg > 0.7:
            outcome_adj = 0.1 if avg > 0.85 else 0.05

    final = min(1.0, max(0.0, base_confidence + doctrine_adj + outcome_adj))
    return ConfidenceAdjustTrace(
        base_confidence=base_confidence,
        doctrine_adjustment=doctrine_adj,
        outcome_adjustment=outcome_adj,
        final_confidence=final,
        signals_consumed=consumed,
    )
