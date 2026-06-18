"""Unit tests for Exploration stage (J11)."""

from harness.schemas.judgment import JudgmentEntry
from judgment.profile import JudgmentProfile
from judgment.stages.exploration import run_exploration


def test_exploration_detects_missed_opportunity() -> None:
    recent = [
        JudgmentEntry(
            brain_id="capital",
            context_id="r1",
            belief="Held on deployment",
            confidence=0.7,
            assumptions=["judgment_outcome:HOLD"],
            changelog=[
                {"action": "outcome_recorded", "details": {"outcome_quality": 0.8}}
            ],
        )
    ]
    trace = run_exploration(JudgmentProfile(domain="capital"), recent)
    assert trace.opportunity_cost_signal is True


def test_exploration_recommends_explore_on_scheduled_run() -> None:
    trace = run_exploration(JudgmentProfile(domain="capital"), [], run_index=0)
    assert trace.recommended_bias == "explore"
    neutral = run_exploration(JudgmentProfile(domain="capital"), [], run_index=1)
    assert neutral.recommended_bias == "neutral"
