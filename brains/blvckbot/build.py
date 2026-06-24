"""Build Brain — produces deliverable specs/briefs for human-run execution.

This brain never executes code or touches a client's systems. Per the
architecture brief, code execution belongs to Cursor, operated by a human
who reviews everything before it goes out — this brain's job is to turn a
job's requirements into a concrete build brief and acceptance checklist that
a human (with Cursor) can execute against, and to review a finished
deliverable against that checklist. Output always requires human review
before delivery.
"""

from __future__ import annotations

from typing import Any

from judgment.profile import JudgmentProfile, ModelConfig

from brains._base.brain import LLMBrain
from brains._base.tools import FunctionTool

BUILD_SYSTEM_PROMPT = (
    "You are the Build Brain for blvckbot, an autonomous freelance agent. "
    "You do not write or execute code — Cursor, operated by a human, does "
    "that. Your job is to turn a job's requirements into a concrete build "
    "brief: scope, a numbered task breakdown, an acceptance checklist, and "
    "an effort estimate (use estimate_build_effort). When reviewing a "
    "finished deliverable against a checklist, use review_against_checklist "
    "and report exactly which items pass and which don't.\n\n"
    "Every build brief or deliverable review you produce requires human "
    "review before delivery to the client. Conclude with PROCEED once the "
    "brief/review is ready for that human review; the harness will route it "
    "to the operator regardless of your recommendation. Use "
    "REQUEST_MORE_EVIDENCE if the requirements are too vague to scope, and "
    "HOLD if the work is outside what blvckbot should attempt."
)


async def _estimate_build_effort(arguments: dict[str, Any]) -> dict[str, Any]:
    """Sum named task-hour estimates into a total effort estimate."""
    tasks = arguments.get("tasks", {})
    if not isinstance(tasks, dict) or not tasks:
        return {"total_hours": 0.0, "note": "no tasks provided"}
    hours = {name: float(h) for name, h in tasks.items() if isinstance(h, (int, float))}
    return {"total_hours": round(sum(hours.values()), 2), "tasks": hours}


async def _review_against_checklist(arguments: dict[str, Any]) -> dict[str, Any]:
    """Mark each checklist item pass/fail based on provided evidence notes."""
    items = arguments.get("items", [])
    if not isinstance(items, list) or not items:
        return {"error": "no checklist items provided"}
    results = []
    passed = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        ok = bool(item.get("passed"))
        passed += int(ok)
        results.append(
            {
                "requirement": item.get("requirement", ""),
                "passed": ok,
                "note": item.get("note", ""),
            }
        )
    return {
        "results": results,
        "passed_count": passed,
        "total_count": len(results),
        "all_passed": passed == len(results) and len(results) > 0,
    }


class BuildBrain(LLMBrain):
    """Scopes build briefs and reviews deliverables. Never executes code itself."""

    brain_id = "build"
    name = "Build Brain"
    description = (
        "Turns job requirements into a build brief/acceptance checklist and reviews "
        "finished deliverables against it. Output always requires human review."
    )
    capabilities = ["build_brief", "deliverable_review"]
    pipeline_participant = False
    judgment_profile = JudgmentProfile(
        domain="build",
        harm_guard_enabled=False,
        human_gate_enabled=True,
        model=ModelConfig(
            preferred_model="claude-sonnet-4-6",
            fallback_models=["gpt-4o"],
            temperature=0.4,
        ),
    )
    system_prompt = BUILD_SYSTEM_PROMPT
    tools = [
        FunctionTool(
            name="estimate_build_effort",
            description="Sum named task-hour estimates into a total effort estimate.",
            input_schema={
                "type": "object",
                "properties": {
                    "tasks": {
                        "type": "object",
                        "description": "Map of task name to estimated hours.",
                    }
                },
                "required": ["tasks"],
            },
            func=_estimate_build_effort,
        ),
        FunctionTool(
            name="review_against_checklist",
            description=(
                "Tally pass/fail results for a deliverable against acceptance "
                "checklist items."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "requirement": {"type": "string"},
                                "passed": {"type": "boolean"},
                                "note": {"type": "string"},
                            },
                        },
                    }
                },
                "required": ["items"],
            },
            func=_review_against_checklist,
        ),
    ]
