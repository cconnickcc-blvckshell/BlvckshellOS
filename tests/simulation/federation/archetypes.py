"""Federation simulation archetypes for judgment promotion gates."""

from __future__ import annotations

from dataclasses import dataclass

from judgment.outcome import JudgmentOutcome


@dataclass(frozen=True, slots=True)
class FederationArchetype:
    """Lightweight brain fixture for isolated judgment experiments."""

    brain_id: str
    domain: str
    scenario: str
    expected_baseline: JudgmentOutcome
    expected_treatment: JudgmentOutcome
    evidence_template: str
    archetype_id: str = ""

    def __post_init__(self) -> None:
        if not self.archetype_id:
            object.__setattr__(self, "archetype_id", self.brain_id)

    def evidence_text(self, run_index: int) -> str:
        """Return scenario evidence with slight run-to-run variance."""
        variance = (run_index % 5) * 0.01
        return self.evidence_template.format(variance=variance)


CAPITAL_BORDERLINE = FederationArchetype(
    brain_id="sim_capital",
    domain="capital",
    scenario="borderline proceed — ROI signal weak positive, risk near cap",
    expected_baseline=JudgmentOutcome.PROCEED,
    expected_treatment=JudgmentOutcome.STAGED_PROCEED,
    evidence_template=(
        "PROCEED — marginal opportunity. ROI: {variance:.2f}. Risk: 0.28. "
        "Weak confidence, borderline case."
    ),
)

COMMANDER_APPROVE = FederationArchetype(
    brain_id="sim_commander",
    domain="coordination",
    scenario="clear approve — high confidence, no risk flags",
    expected_baseline=JudgmentOutcome.PROCEED,
    expected_treatment=JudgmentOutcome.PROCEED,
    evidence_template="PROCEED — clear approve. ROI: 0.15. Risk: 0.08. Strong confidence.",
)

CAPITAL_HOLD = FederationArchetype(
    brain_id="sim_capital_hold",
    domain="capital",
    scenario="harm guard trigger — negative ROI evidence",
    expected_baseline=JudgmentOutcome.PROCEED,
    expected_treatment=JudgmentOutcome.HOLD,
    evidence_template="PROCEED full deployment. negative roi. Risk: 0.45. Unprofitable.",
)

SENTINEL_EVIDENCE_GAP = FederationArchetype(
    brain_id="sim_sentinel",
    domain="risk",
    scenario="evidence gap — contested signals, low confidence",
    expected_baseline=JudgmentOutcome.PROCEED,
    expected_treatment=JudgmentOutcome.REQUEST_MORE_EVIDENCE,
    evidence_template="Need more data. Insufficient evidence. Unclear conflicting signals.",
)

ALL_ARCHETYPES = (
    CAPITAL_BORDERLINE,
    COMMANDER_APPROVE,
    CAPITAL_HOLD,
    SENTINEL_EVIDENCE_GAP,
)
