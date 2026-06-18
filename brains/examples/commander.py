"""Commander Brain — turns a validated idea into an execution plan."""

from __future__ import annotations

from judgment.profile import JudgmentProfile

from brains._base.brain import LLMBrain


class CommanderBrain(LLMBrain):
    """Builds concrete, sequenced execution plans."""

    brain_id = "commander"
    name = "Commander Brain"
    description = "Builds the execution plan: milestones, sequencing, and first moves"
    capabilities = ["execution_planning", "milestone_planning", "resource_planning"]
    judgment_profile = JudgmentProfile(domain="commander", harm_guard_enabled=False)
    system_prompt = (
        "You are the Commander Brain. You convert intent into action. Produce a "
        "crisp execution plan: phases, the critical path, concrete first moves for "
        "the next steps, and the key resources or dependencies required. Favor "
        "decisive sequencing over exhaustive detail. End with the single highest-"
        "leverage next action."
    )
