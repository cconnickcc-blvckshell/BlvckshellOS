"""Venture Brain — validates ideas and assesses feasibility."""

from __future__ import annotations

from harness.schemas.task import TaskPayload

from brains._base.worker import LLMWorkerBrain


class VentureBrain(LLMWorkerBrain):
    """Assesses whether an idea is sound, feasible, and worth pursuing."""

    brain_id = "venture"
    name = "Venture Brain"
    description = "Validates ideas, assesses feasibility, and surfaces key risks."
    capabilities = ["validate_idea", "assess_feasibility"]
    model = "stub-1"
    default_confidence = 0.65

    def system_prompt(self) -> str:
        """Return the Venture Brain's analyst role prompt."""
        return (
            "Venture Brain. You are a hard-nosed early-stage analyst. Given an idea, "
            "judge feasibility, market reality, and the single biggest risk. Be decisive: "
            "end with a clear go / no-go / conditional recommendation."
        )

    def belief_for(self, task: TaskPayload, loop_content: str) -> str:
        """Record a feasibility belief for the ledger."""
        return f"Feasibility assessment formed for: {task.objective[:160]}"
