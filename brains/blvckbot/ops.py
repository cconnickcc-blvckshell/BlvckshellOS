"""Ops Brain — status monitoring, delivery packaging, and financial/account flags.

Payment and account actions are never taken by this brain. It only packages
what a human needs to act (what changed, what's ready, what needs a
decision) and always surfaces it for operator confirmation.
"""

from __future__ import annotations

from typing import Any

from judgment.profile import JudgmentProfile, ModelConfig

from brains._base.brain import LLMBrain
from brains._base.tools import FunctionTool

OPS_SYSTEM_PROMPT = (
    "You are the Ops Brain for blvckbot, an autonomous freelance agent. You "
    "monitor pipeline status, package finished deliverables for handoff, and "
    "flag any financial or account action a human needs to take (accepting a "
    "contract, withdrawing funds, declining a job, responding to a client "
    "payment dispute, etc).\n\n"
    "You never execute a financial or account action yourself — use "
    "flag_financial_action to describe exactly what action is needed and why, "
    "and use package_deliverable to summarize what's ready to ship. Use "
    "summarize_run_status to report where a run currently stands.\n\n"
    "Every output you produce requires human confirmation before anything "
    "happens in the real world. Conclude with PROCEED once your status "
    "summary, package, or flag is ready for that human review; the harness "
    "will route it to the operator regardless of your recommendation. Use "
    "REQUEST_MORE_EVIDENCE if you don't have enough information to report "
    "accurately, and HOLD if the situation looks unsafe to proceed on at all."
)


async def _summarize_run_status(arguments: dict[str, Any]) -> dict[str, Any]:
    """Roll task statuses up into a one-line run summary."""
    statuses = arguments.get("task_statuses", {})
    if not isinstance(statuses, dict) or not statuses:
        return {"summary": "no tasks to report", "counts": {}}
    counts: dict[str, int] = {}
    for status in statuses.values():
        counts[status] = counts.get(status, 0) + 1
    total = sum(counts.values())
    done = counts.get("COMPLETED", 0)
    return {
        "summary": f"{done}/{total} tasks completed",
        "counts": counts,
    }


async def _package_deliverable(arguments: dict[str, Any]) -> dict[str, Any]:
    """Assemble a handoff package description from deliverable parts."""
    files = arguments.get("files", [])
    notes = arguments.get("notes", "")
    if not files and not notes:
        return {"error": "no files or notes provided to package"}
    return {
        "files": files,
        "notes": notes,
        "ready_for_review": True,
    }


async def _flag_financial_action(arguments: dict[str, Any]) -> dict[str, Any]:
    """Describe a financial/account action for human confirmation. Never executes it."""
    action = arguments.get("action", "")
    reason = arguments.get("reason", "")
    amount = arguments.get("amount")
    if not action:
        return {"error": "action is required"}
    return {
        "action": action,
        "reason": reason,
        "amount": amount,
        "requires_human_confirmation": True,
        "executed": False,
    }


class OpsBrain(LLMBrain):
    """Monitors run status, packages deliverables, and flags financial/account actions."""

    brain_id = "ops"
    name = "Ops Brain"
    description = (
        "Reports pipeline status, packages finished deliverables for handoff, and "
        "flags financial/account actions for the human — never executes them."
    )
    capabilities = ["status_monitoring", "delivery_packaging", "financial_action_flagging"]
    pipeline_participant = False
    judgment_profile = JudgmentProfile(
        domain="ops",
        harm_guard_enabled=False,
        human_gate_enabled=True,
        model=ModelConfig(
            preferred_model="claude-sonnet-4-6",
            fallback_models=["gpt-4o"],
            temperature=0.3,
        ),
    )
    system_prompt = OPS_SYSTEM_PROMPT
    tools = [
        FunctionTool(
            name="summarize_run_status",
            description="Roll a map of task_id to status into a one-line run summary.",
            input_schema={
                "type": "object",
                "properties": {
                    "task_statuses": {
                        "type": "object",
                        "description": "Map of task id to status string.",
                    }
                },
                "required": ["task_statuses"],
            },
            func=_summarize_run_status,
        ),
        FunctionTool(
            name="package_deliverable",
            description="Assemble a handoff package description from deliverable files/notes.",
            input_schema={
                "type": "object",
                "properties": {
                    "files": {"type": "array", "items": {"type": "string"}},
                    "notes": {"type": "string"},
                },
            },
            func=_package_deliverable,
        ),
        FunctionTool(
            name="flag_financial_action",
            description=(
                "Describe a financial or account action that needs human confirmation. "
                "This never executes the action — it only flags it for the operator."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "What needs to happen."},
                    "reason": {"type": "string"},
                    "amount": {"type": "number"},
                },
                "required": ["action"],
            },
            func=_flag_financial_action,
        ),
    ]
