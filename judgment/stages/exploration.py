"""Exploration — bandit + opportunity cost pre-decision (J11)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from harness.schemas.judgment import JudgmentEntry

from judgment.outcome import JudgmentOutcome
from judgment.profile import JudgmentProfile


@dataclass(slots=True)
class ExplorationTrace:
    """Trace output from the Exploration stage."""

    exploration_bonus: float
    opportunity_cost_signal: bool
    recommended_bias: str
    signals_consumed: list[str] = field(default_factory=list)


def _outcome_quality(entry: JudgmentEntry) -> float | None:
    for change in reversed(entry.changelog):
        if change.get("action") == "outcome_recorded":
            quality = (change.get("details") or {}).get("outcome_quality")
            if quality is not None:
                return float(quality)
    return None


def _decision(entry: JudgmentEntry) -> JudgmentOutcome | None:
    for assumption in entry.assumptions:
        if assumption.startswith("judgment_outcome:"):
            try:
                return JudgmentOutcome(assumption.split(":", 1)[1])
            except ValueError:
                return None
    return None


def run_exploration(
    profile: JudgmentProfile,
    recent: list[JudgmentEntry],
    *,
    run_index: int = 0,
) -> ExplorationTrace:
    """UCB-style exploration bonus and missed-opportunity detection."""
    consumed: list[str] = []
    window = recent[:20]
    if not window:
        return ExplorationTrace(
            exploration_bonus=0.5,
            opportunity_cost_signal=False,
            recommended_bias="explore" if run_index % 5 == 0 else "neutral",
            signals_consumed=["ledger.empty"],
        )

    consumed.append("ledger.recent_decisions")
    total = len(window)
    domain_counts: dict[str, int] = {}
    for entry in window:
        domain_counts[entry.brain_id] = domain_counts.get(entry.brain_id, 0) + 1

    count = domain_counts.get(profile.domain, 0)
    exploitation = count / total if total else 0.0
    exploration_bonus = math.sqrt(math.log(max(total, 1)) / max(count, 1))
    exploration_bonus = min(1.0, max(0.0, exploration_bonus / 3.0))

    opportunity = False
    for entry in window:
        decision = _decision(entry)
        quality = _outcome_quality(entry)
        if decision == JudgmentOutcome.HOLD and quality is not None and quality > 0.5:
            opportunity = True
            consumed.append("ledger.missed_opportunity")
            break

    if exploration_bonus >= 0.6 or run_index % 5 == 0:
        bias = "explore"
    elif exploitation >= 0.7:
        bias = "exploit"
    else:
        bias = "neutral"

    return ExplorationTrace(
        exploration_bonus=exploration_bonus,
        opportunity_cost_signal=opportunity,
        recommended_bias=bias,
        signals_consumed=consumed,
    )
