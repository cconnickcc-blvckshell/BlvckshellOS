"""Unit tests for Foundation confidence adjustment (J9)."""

from harness.schemas.brain_info import BrainContext
from harness.schemas.judgment import JudgmentEntry
from judgment.profile import JudgmentProfile
from judgment.stages.confidence import adjust_confidence


def test_confidence_boosted_by_high_doctrine() -> None:
    context = BrainContext(
        context_id="c1",
        brain_id="venture",
        doctrine=[
            JudgmentEntry(
                brain_id="venture",
                context_id="d1",
                belief="Markets favor AI tools",
                confidence=0.9,
            )
        ],
    )
    trace = adjust_confidence(JudgmentProfile(domain="venture"), context)
    assert trace.doctrine_adjustment >= 0.05
    assert trace.final_confidence > trace.base_confidence


def test_confidence_penalized_by_poor_recent_outcomes() -> None:
    context = BrainContext(
        context_id="c1",
        brain_id="capital",
        recent_judgments=[
            JudgmentEntry(
                brain_id="capital",
                context_id="r1",
                belief="Prior allocation",
                confidence=0.8,
                changelog=[
                    {"action": "outcome_recorded", "details": {"outcome_quality": -0.2}}
                ],
            )
        ],
    )
    trace = adjust_confidence(JudgmentProfile(domain="capital"), context)
    assert trace.outcome_adjustment < 0
    assert trace.final_confidence < trace.base_confidence
