"""Proposal Brain — drafts freelance proposals. Drafts only; never sends."""

from __future__ import annotations

from typing import Any

from judgment.profile import JudgmentProfile, ModelConfig

from brains._base.brain import LLMBrain
from brains._base.tools import FunctionTool

PROPOSAL_SYSTEM_PROMPT = (
    "You are the Proposal Brain for blvckbot, an autonomous freelance agent. "
    "Your only job is to draft a personalized proposal for a given lead — you "
    "never send anything, you only produce a draft for a human to review.\n\n"
    "Write as if addressing the client directly: acknowledge their specific "
    "need (not a generic template), state a concrete approach, and propose a "
    "price using estimate_price_band when budget/hours information is "
    "available. Keep it tight — clients skim.\n\n"
    "Every proposal you draft requires human approval before it is sent. "
    "Conclude your reasoning with PROCEED once the draft is ready for review; "
    "the harness will route it to the operator regardless of your "
    "recommendation. Use REQUEST_MORE_EVIDENCE only if the lead has too "
    "little information to draft against, and HOLD if you believe this lead "
    "should not be pursued at all."
)


async def _estimate_price_band(arguments: dict[str, Any]) -> dict[str, Any]:
    """Estimate a low/target/high price band from budget and/or hourly inputs."""
    budget = arguments.get("client_budget")
    hours = arguments.get("estimated_hours")
    rate = arguments.get("hourly_rate")

    if budget is not None:
        budget = float(budget)
        return {
            "low": round(budget * 0.85, 2),
            "target": round(budget, 2),
            "high": round(budget * 1.1, 2),
            "basis": "client_budget",
        }
    if hours is not None and rate is not None:
        cost = float(hours) * float(rate)
        return {
            "low": round(cost * 0.9, 2),
            "target": round(cost, 2),
            "high": round(cost * 1.2, 2),
            "basis": "hours_times_rate",
        }
    return {"error": "need either client_budget or both estimated_hours and hourly_rate"}


class ProposalBrain(LLMBrain):
    """Drafts personalized freelance proposals. Output always requires human approval."""

    brain_id = "proposal"
    name = "Proposal Brain"
    description = (
        "Drafts personalized freelance proposals from a scored lead. Never sends "
        "anything — every draft is gated to human approval before it goes out."
    )
    capabilities = ["proposal_drafting"]
    pipeline_participant = False
    judgment_profile = JudgmentProfile(
        domain="proposal",
        harm_guard_enabled=False,
        human_gate_enabled=True,
        model=ModelConfig(
            preferred_model="claude-sonnet-4-6",
            fallback_models=["gpt-4o"],
            temperature=0.6,
        ),
    )
    system_prompt = PROPOSAL_SYSTEM_PROMPT
    tools = [
        FunctionTool(
            name="estimate_price_band",
            description=(
                "Estimate a low/target/high price band from a client's stated "
                "budget, or from estimated hours and an hourly rate."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "client_budget": {"type": "number"},
                    "estimated_hours": {"type": "number"},
                    "hourly_rate": {"type": "number"},
                },
            },
            func=_estimate_price_band,
        )
    ]
