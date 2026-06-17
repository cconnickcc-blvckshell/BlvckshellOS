"""Capital Brain (stub) — flags capital/financial target domains.

This is intentionally a stub: it advertises its domain and flags relevance so
the orchestrator can plan around it, without yet performing deep capital work.
"""

from __future__ import annotations

from harness.schemas.task import TaskPayload

from brains._base.worker import LLMWorkerBrain


class CapitalBrain(LLMWorkerBrain):
    """Stub brain that flags an objective as a capital/financial target domain."""

    brain_id = "capital"
    name = "Capital Brain"
    description = "Stub: flags capital/financial target domains for later deep work."
    capabilities = ["flag_capital_domain"]
    model = "stub-1"
    default_confidence = 0.4

    def system_prompt(self) -> str:
        """Return the Capital Brain's domain-flagging role prompt."""
        return (
            "Capital Brain (stub). Identify whether the objective touches capital, "
            "funding, or financial markets, and flag it as a target domain for future "
            "deep analysis. Keep it to one paragraph."
        )

    def belief_for(self, task: TaskPayload, loop_content: str) -> str:
        """Record a domain-flag belief for the ledger."""
        return f"Flagged as capital target domain (stub): {task.objective[:140]}"
