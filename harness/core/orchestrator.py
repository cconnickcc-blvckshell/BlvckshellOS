"""The Orchestrator — the harness's internal routing engine.

This is **not** a brain. It does not extend ``BaseBrain``, does not register
with the registry, and does not appear in the brain-orb view. It is the
harness's own mechanical intelligence:

- :meth:`plan` decomposes an :class:`~harness.schemas.objective.Objective` into
  routed :class:`~harness.schemas.task.Task` objects, validated against the live
  registry so it never routes to a capability no brain advertises.
- :meth:`synthesize` aggregates task results into a single coherent briefing.

CKOS — a future intelligent brain that will sit *above* the harness and direct
it — is a different thing entirely and deliberately lives outside the harness.
"""

from __future__ import annotations

import json

from harness.core.llm import LLMClient
from harness.core.memory import SharedMemory
from harness.core.observer import Observer
from harness.core.orchestrator_prompts import (
    ORCHESTRATOR_SYSTEM_PROMPT,
    PLANNING_INSTRUCTIONS,
    SYNTHESIS_INSTRUCTIONS,
)
from harness.core.registry import BrainRegistry
from harness.logging_config import get_logger
from harness.schemas.brain_info import BrainInfo
from harness.schemas.judgment import JudgmentEntry
from harness.schemas.objective import Objective, Run
from harness.schemas.result import Result
from harness.schemas.task import Task

logger = get_logger("orchestrator")


class Orchestrator:
    """Plans and synthesizes pipeline runs. A harness-internal component."""

    def __init__(
        self,
        *,
        llm: LLMClient,
        registry: BrainRegistry,
        memory: SharedMemory,
        observer: Observer,
        model: str | None = None,
    ) -> None:
        """Create the orchestrator.

        Args:
            llm: The LLM client used for planning and synthesis.
            registry: The live brain registry (the only source of valid routes).
            memory: Shared memory for logging routing judgments.
            observer: The Observer for audit logging.
            model: Optional model override; ``None`` uses the LLM client default.
        """
        self._llm = llm
        self._registry = registry
        self._memory = memory
        self._observer = observer
        self._model = model

    async def plan(self, objective: Objective, run: Run) -> list[Task]:
        """Decompose an objective into routed tasks for a run.

        Queries the registry for available brains, asks the LLM for a JSON plan,
        validates every capability against the live registry, and falls back to a
        deterministic heuristic (one task per registered brain) if the LLM is
        unavailable or returns an unusable plan. The routing decision is logged
        to the Judgment Ledger. Returned tasks have ``run_id`` and
        ``objective_id`` populated.

        Args:
            objective: The operator's objective.
            run: The run the tasks belong to.

        Returns:
            A list of routed :class:`Task` objects (possibly empty).
        """
        brains = [b for b in await self._registry.list_all() if b.pipeline_participant]
        if not brains:
            logger.warning("orchestrator_no_brains", run_id=run.run_id)
            return []

        capability_to_brain: dict[str, str] = {}
        for brain in brains:
            for cap in brain.capabilities:
                capability_to_brain.setdefault(cap, brain.brain_id)

        tasks = await self._llm_plan(objective.statement, brains, capability_to_brain)
        if not tasks:
            tasks = self._heuristic_plan(objective.statement, brains)

        for task in tasks:
            task.run_id = run.run_id
            task.objective_id = objective.objective_id

        await self._log_routing(objective, run, tasks)
        return tasks

    async def _llm_plan(
        self, statement: str, brains: list[BrainInfo], capability_to_brain: dict[str, str]
    ) -> list[Task]:
        """Ask the LLM for a JSON plan and validate it against the registry."""
        catalog = "\n".join(
            f"- brain '{b.brain_id}' ({b.name}): capabilities={b.capabilities} — {b.description}"
            for b in brains
        )
        prompt = PLANNING_INSTRUCTIONS.format(idea=statement, brain_catalog=catalog)
        response = await self._llm.complete(
            system=ORCHESTRATOR_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            model=self._model,
        )
        payload = _extract_json(response.text)
        if not payload or "tasks" not in payload:
            return []

        raw_tasks = payload.get("tasks") or []
        built: list[Task] = []
        for raw in raw_tasks:
            capability = raw.get("capability")
            brain_id = capability_to_brain.get(capability)
            if brain_id is None:
                continue
            built.append(
                Task(
                    capability=capability,
                    objective=raw.get("objective", statement),
                    assigned_brain=brain_id,
                )
            )

        # Resolve depends_on indices into task ids after all tasks exist.
        for built_task, raw in zip(built, raw_tasks, strict=False):
            for idx in raw.get("depends_on", []):
                if isinstance(idx, int) and 0 <= idx < len(built):
                    built_task.depends_on.append(built[idx].id)
        return built

    def _heuristic_plan(self, statement: str, brains: list[BrainInfo]) -> list[Task]:
        """Deterministic fallback: route the objective to every registered brain."""
        tasks: list[Task] = []
        for brain in brains:
            capability = brain.capabilities[0] if brain.capabilities else "general"
            tasks.append(
                Task(
                    capability=capability,
                    objective=f"{brain.description.rstrip('.')}. Apply this to: {statement}",
                    assigned_brain=brain.brain_id,
                )
            )
        return tasks

    async def _log_routing(self, objective: Objective, run: Run, tasks: list[Task]) -> None:
        """Log the routing decision and its reasoning to the Judgment Ledger."""
        routes = [f"{t.capability} -> {t.assigned_brain}" for t in tasks]
        entry = JudgmentEntry(
            brain_id="orchestrator",
            context_id=run.run_id,
            belief=f"Decomposed objective into {len(tasks)} tasks: {', '.join(routes)}",
            confidence=0.75,
            evidence=[f"registered_brain:{t.assigned_brain}" for t in tasks],
            assumptions=["Each routed brain can handle its assigned capability."],
        )
        await self._memory.record_judgment(entry)

    async def synthesize(self, objective: Objective, run: Run, results: list[Result]) -> str:
        """Aggregate task results into a coherent operator briefing.

        Args:
            objective: The original objective.
            run: The run the results belong to.
            results: The results returned by the brains.

        Returns:
            A synthesized briefing string (deterministic fallback when offline).
        """
        if not results:
            return "No brain produced a result for this objective."

        rendered = "\n\n".join(
            f"[{r.brain_id}] ({r.status.value})\n{r.summary or r.error or '(no summary)'}"
            for r in results
        )
        prompt = SYNTHESIS_INSTRUCTIONS.format(idea=objective.statement, results=rendered)
        response = await self._llm.complete(
            system=ORCHESTRATOR_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            model=self._model,
        )
        synthesis = response.text.strip()
        if not synthesis or synthesis.startswith("[offline-analysis]"):
            ok = [r for r in results if r.succeeded]
            lines = [f"Synthesis for: {objective.statement}", ""]
            lines += [f"- {r.brain_id}: {r.summary}" for r in ok]
            failed = [r for r in results if not r.succeeded]
            if failed:
                lines.append("")
                lines += [f"- BLOCKED {r.brain_id}: {r.error}" for r in failed]
            synthesis = "\n".join(lines)
        return synthesis


def _extract_json(text: str) -> dict | None:
    """Best-effort extraction of a JSON object from model output.

    Args:
        text: Raw model text that should contain a JSON object.

    Returns:
        The parsed dict, or ``None`` if no valid JSON object was found.
    """
    text = text.strip()
    if not text:
        return None
    if text.startswith("```"):
        text = text.strip("`")
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None
