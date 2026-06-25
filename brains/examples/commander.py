"""Commander Brain — turns a validated idea into an execution plan."""

from __future__ import annotations

from judgment.profile import JudgmentProfile

from brains._base.brain import LLMBrain
from brains._base.tools import web_search_tool


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
        "decisive sequencing over exhaustive detail.\n\n"
        "Use web_search before citing any real tool, vendor, pricing, or "
        "comparable-launch timeline as fact — never invent one from memory. Sequencing "
        "logic (what must happen before what) is yours to reason about, but specific "
        "day-count estimates are not measured facts — label them clearly as estimates, "
        "not findings, and don't dress them up with false precision.\n\n"
        "End with the single highest-leverage next action."
    )
    tools = [web_search_tool()]
