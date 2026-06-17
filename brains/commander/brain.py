"""Commander Brain — turns validated ideas into execution plans."""

from __future__ import annotations

from harness.schemas.task import TaskPayload

from brains._base.worker import LLMWorkerBrain


class CommanderBrain(LLMWorkerBrain):
    """Produces a concrete, sequenced execution plan for an objective."""

    brain_id = "commander"
    name = "Commander Brain"
    description = "Builds concrete, sequenced execution plans from objectives."
    capabilities = ["build_execution_plan", "plan"]
    model = "stub-1"
    default_confidence = 0.6

    def system_prompt(self) -> str:
        """Return the Commander Brain's planner role prompt."""
        return (
            "Commander Brain. You convert an objective into an execution plan: the first "
            "three concrete moves, the resources each needs, and the earliest measurable "
            "milestone. Bias toward action and sequencing, not theory."
        )

    def belief_for(self, task: TaskPayload, loop_content: str) -> str:
        """Record an execution-plan belief for the ledger."""
        return f"Execution plan drafted for: {task.objective[:160]}"
