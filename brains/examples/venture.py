"""Venture Brain — validates ideas and assesses feasibility."""

from __future__ import annotations

from typing import Any

from judgment.profile import JudgmentProfile, ModelConfig

from brains._base.brain import LLMBrain
from brains._base.tools import FunctionTool


async def _feasibility_score(arguments: dict[str, Any]) -> dict[str, Any]:
    """Compute a crude feasibility score from named factors (0-10 each)."""
    factors = arguments.get("factors", {})
    if not isinstance(factors, dict) or not factors:
        return {"score": 0.0, "note": "no factors provided"}
    values = [float(v) for v in factors.values() if isinstance(v, (int, float))]
    score = round(sum(values) / (len(values) or 1), 2)
    return {"score": score, "max": 10.0, "factors": factors}


class VentureBrain(LLMBrain):
    """Assesses whether an idea is worth pursuing and how feasible it is."""

    brain_id = "venture"
    name = "Venture Brain"
    description = "Validates the idea and assesses feasibility, market, and risk"
    capabilities = ["idea_validation", "feasibility_assessment", "market_analysis"]
    judgment_profile = JudgmentProfile(
        domain="venture",
        harm_guard_enabled=False,
        model=ModelConfig(
            preferred_model="claude-sonnet-4-6",
            fallback_models=["gpt-4o"],
            temperature=0.7,
        ),
    )
    system_prompt = (
        "You are the Venture Brain. You rigorously validate ideas: market reality, "
        "feasibility, competitive moat, and the top risks. Be skeptical but fair. "
        "Use the feasibility_score tool when you want a numeric read on factors. "
        "End with a clear GO / NO-GO / CONDITIONAL recommendation and the single "
        "most important reason."
    )
    tools = [
        FunctionTool(
            name="feasibility_score",
            description="Average a set of 0-10 feasibility factors into one score.",
            input_schema={
                "type": "object",
                "properties": {
                    "factors": {
                        "type": "object",
                        "description": "Map of factor name to a 0-10 rating.",
                    }
                },
                "required": ["factors"],
            },
            func=_feasibility_score,
        )
    ]
