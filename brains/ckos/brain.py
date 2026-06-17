"""CKOS — the orchestrator brain.

CKOS is not just another brain; it is the conductor. It receives intake,
understands intent, decomposes ideas into discrete tasks, and routes each to a
registered specialist brain. It then aggregates the results into a single
coherent output and logs its routing decisions to the Judgment Ledger.

The mechanical dispatch/collection is delegated to
:class:`~harness.core.router.PipelineRouter`; CKOS supplies the intelligence:
:meth:`plan` and :meth:`synthesize`.
"""

from __future__ import annotations

import json

from harness.logging_config import get_logger
from harness.schemas.brain_info import BrainContext
from harness.schemas.judgment import JudgmentEntry
from harness.schemas.message import HarnessMessage, MessageType
from harness.schemas.result import Result, ResultStatus
from harness.schemas.task import Task

from brains._base.brain import BaseBrain, BrainRuntime
from brains.ckos.prompts import (
    CKOS_SYSTEM_PROMPT,
    PLANNING_INSTRUCTIONS,
    SYNTHESIS_INSTRUCTIONS,
)

logger = get_logger("ckos")


class CKOSBrain(BaseBrain):
    """The Chief Knowledge & Operating System orchestrator."""

    brain_id = "ckos"
    name = "CKOS"
    description = "Chief Knowledge & Operating System — decomposes intent and routes work."
    capabilities = ["orchestration", "intent_decomposition", "synthesis"]
    model = "ckos"

    def __init__(self, runtime: BrainRuntime) -> None:
        """Bind CKOS and pin its model to the configured Anthropic model."""
        super().__init__(runtime)
        self.model = runtime.settings.anthropic_model

    async def get_context(self, context_id: str) -> BrainContext:
        """Load CKOS's working context from shared memory."""
        return await self.runtime.memory.load_context(context_id, self.brain_id)

    async def log_judgment(self, entry: JudgmentEntry) -> None:
        """Record a routing decision to the Judgment Ledger."""
        await self.runtime.memory.record_judgment(entry)

    async def _worker_catalog(self) -> list:
        """Return registered brains CKOS may route to (excludes CKOS itself)."""
        brains = await self.runtime.registry.list_all()
        return [b for b in brains if b.brain_id != self.brain_id]

    async def plan(self, idea: str, context_id: str) -> list[Task]:
        """Decompose an idea into routed tasks.

        Uses the LLM to produce a JSON plan, validated against the live registry
        so CKOS never routes to a non-existent capability. Falls back to a
        deterministic heuristic (one task per registered brain) when the LLM is
        unavailable or returns an unusable plan.

        Args:
            idea: The operator's idea/intent.
            context_id: The pipeline run identifier.

        Returns:
            A list of routed :class:`Task` objects.
        """
        workers = await self._worker_catalog()
        if not workers:
            logger.warning("ckos_no_workers", context_id=context_id)
            return []

        capability_to_brain: dict[str, str] = {}
        for brain in workers:
            for cap in brain.capabilities:
                capability_to_brain.setdefault(cap, brain.brain_id)

        tasks = await self._llm_plan(idea, workers, capability_to_brain)
        if not tasks:
            tasks = self._heuristic_plan(idea, workers)

        await self._log_routing(idea, tasks, context_id)
        return tasks

    async def _llm_plan(
        self, idea: str, workers: list, capability_to_brain: dict[str, str]
    ) -> list[Task]:
        """Ask the LLM for a JSON plan and validate it against the registry."""
        catalog = "\n".join(
            f"- brain '{b.brain_id}' ({b.name}): capabilities={b.capabilities} — {b.description}"
            for b in workers
        )
        prompt = PLANNING_INSTRUCTIONS.format(idea=idea, brain_catalog=catalog)
        response = await self.runtime.llm.complete(
            system=CKOS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            model=self.model if self.model != "ckos" else None,
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
                    objective=raw.get("objective", idea),
                    assigned_brain=brain_id,
                )
            )

        # Resolve depends_on indices into task ids after all tasks exist.
        for built_task, raw in zip(built, raw_tasks, strict=False):
            for idx in raw.get("depends_on", []):
                if isinstance(idx, int) and 0 <= idx < len(built):
                    built_task.depends_on.append(built[idx].id)
        return built

    def _heuristic_plan(self, idea: str, workers: list) -> list[Task]:
        """Deterministic fallback: route the idea to every registered brain."""
        tasks: list[Task] = []
        for brain in workers:
            capability = brain.capabilities[0] if brain.capabilities else "general"
            tasks.append(
                Task(
                    capability=capability,
                    objective=f"{brain.description.rstrip('.')}. Apply this to: {idea}",
                    assigned_brain=brain.brain_id,
                )
            )
        return tasks

    async def _log_routing(self, idea: str, tasks: list[Task], context_id: str) -> None:
        """Log the routing decision and its reasoning to the Judgment Ledger."""
        routes = [f"{t.capability} -> {t.assigned_brain}" for t in tasks]
        entry = JudgmentEntry(
            brain_id=self.brain_id,
            context_id=context_id,
            belief=f"Decomposed idea into {len(tasks)} tasks: {', '.join(routes)}",
            confidence=0.75,
            evidence=[f"registered_brain:{t.assigned_brain}" for t in tasks],
            assumptions=["Each routed brain can handle its assigned capability."],
        )
        await self.log_judgment(entry)

    async def synthesize(self, idea: str, results: list[Result], context_id: str) -> str:
        """Aggregate brain results into a coherent operator briefing.

        Args:
            idea: The original operator idea.
            results: The results returned by the brains.
            context_id: The pipeline run identifier.

        Returns:
            A synthesized briefing string.
        """
        if not results:
            return "No brain produced a result for this idea."

        rendered = "\n\n".join(
            f"[{r.brain_id}] ({r.status.value})\n{r.summary or r.error or '(no summary)'}"
            for r in results
        )
        prompt = SYNTHESIS_INSTRUCTIONS.format(idea=idea, results=rendered)
        response = await self.runtime.llm.complete(
            system=CKOS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            model=self.model if self.model != "ckos" else None,
        )
        synthesis = response.text.strip()
        if not synthesis or synthesis.startswith("[offline-analysis]"):
            # Deterministic fallback synthesis for offline operation.
            ok = [r for r in results if r.succeeded]
            lines = [f"Synthesis for: {idea}", ""]
            lines += [f"- {r.brain_id}: {r.summary}" for r in ok]
            failed = [r for r in results if not r.succeeded]
            if failed:
                lines.append("")
                lines += [f"- BLOCKED {r.brain_id}: {r.error}" for r in failed]
            synthesis = "\n".join(lines)
        return synthesis

    async def handle_task(self, task: HarnessMessage) -> HarnessMessage:
        """Run a full pipeline when CKOS receives an intake task on the bus.

        This lets CKOS be triggered directly over the bus. The harness API
        normally drives pipelines via :class:`~harness.core.router.PipelineRouter`
        for streaming/tracking, but this keeps CKOS self-sufficient.
        """
        from harness.core.router import PipelineRouter

        idea = task.payload.get("idea") or task.payload.get("objective", "")
        router = PipelineRouter(
            bus=self.runtime.bus,
            memory=self.runtime.memory,
            observer=self.runtime.observer,
            orchestrator=self,
        )
        run = await router.run(idea, task.context_id, source=task.source)
        status = (
            ResultStatus.NEEDS_OPERATOR
            if run.status == "NEEDS_OPERATOR"
            else ResultStatus.SUCCESS
        )
        result = Result(
            task_id=task.payload.get("id", task.id),
            brain_id=self.brain_id,
            status=status,
            output={"pipeline": run.to_dict()},
            summary=run.output[:280],
        )
        return task.reply(
            source=self.brain_id,
            message_type=MessageType.RESULT,
            payload=result.model_dump(mode="json"),
        )


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
    # Strip markdown fences if present.
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
