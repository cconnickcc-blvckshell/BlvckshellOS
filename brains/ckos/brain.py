"""CKOS — the orchestrator brain.

CKOS is not just another brain; it is the conductor. It receives all intake,
understands intent, decomposes it into discrete tasks, routes each to the right
brain, monitors progress, aggregates results, and decides when a pipeline is
complete — logging its reasoning to the Judgment Ledger throughout.
"""

from __future__ import annotations

import json
import re
from typing import Any

from harness.core.inference import LLMMessage
from harness.core.logging import get_logger
from harness.core.router import CKOSRouter
from harness.core.runtime import HarnessRuntime
from harness.schemas.brain import BrainContext
from harness.schemas.event import EventType
from harness.schemas.judgment import JudgmentEntry
from harness.schemas.message import HarnessMessage, MessageType
from harness.schemas.result import ResultPayload, ResultStatus
from harness.schemas.task import TaskPayload

from brains._base.brain import BaseBrain
from brains.ckos.prompts import (
    CKOS_SYNTHESIS_PROMPT,
    CKOS_SYSTEM_PROMPT,
    build_decomposition_prompt,
)
from brains.ckos.tools import ListBrainsTool

logger = get_logger(__name__)


class CKOSBrain(BaseBrain):
    """The orchestrator: decompose, route, aggregate, decide completion."""

    brain_id = "ckos"
    name = "CKOS"
    description = "Chief Knowledge & Operating System — the orchestrator brain."
    capabilities = ["orchestrate", "decompose", "route", "aggregate"]
    model = "stub-1"

    def __init__(self, runtime: HarnessRuntime) -> None:
        """Wire CKOS with a router and an introspection tool."""
        super().__init__(runtime, tools=[ListBrainsTool(runtime.registry)])
        self.router = CKOSRouter(runtime)

    def system_prompt(self) -> str:
        """Return the CKOS conductor system prompt."""
        return CKOS_SYSTEM_PROMPT

    async def get_context(self, context_id: str) -> BrainContext:
        """Load orchestration context from shared memory."""
        return await self.default_context(context_id)

    async def log_judgment(self, entry: JudgmentEntry) -> None:
        """Record a routing/orchestration judgment to the ledger."""
        await self.default_log_judgment(entry)

    async def start(self) -> None:
        """Start the brain and its result-correlation router."""
        await super().start()
        await self.router.start()

    async def stop(self) -> None:
        """Stop the router and the brain."""
        await self.router.stop()
        await super().stop()

    async def handle_task(self, task: HarnessMessage) -> HarnessMessage:
        """Orchestrate a full pipeline from a single intake message.

        Args:
            task: The intake ``TASK`` message carrying the operator objective.

        Returns:
            A ``RESULT`` message with the synthesized, aggregated output.
        """
        objective = task.payload.get("objective", "")
        context_id = task.context_id

        await self.runtime.observer.record(
            EventType.PIPELINE_STARTED,
            source=self.brain_id,
            context_id=context_id,
            message=objective[:160],
        )
        await self.runtime.memory.put_working(context_id, "objective", objective)

        plan = await self.decompose(objective, context_id)
        await self.runtime.memory.put_working(
            context_id, "plan", [t.model_dump(mode="json") for t in plan]
        )

        await self.log_judgment(
            JudgmentEntry(
                brain_id=self.brain_id,
                context_id=context_id,
                belief=(
                    f"Decomposed objective into {len(plan)} task(s): "
                    f"{[t.capability for t in plan]}"
                ),
                confidence=0.7 if plan else 0.2,
                evidence=[f"registered_capabilities={await self.runtime.registry.capabilities()}"],
                assumptions=["registered capabilities are accurate and healthy"],
            )
        )

        if not plan:
            return self._escalation(task, objective)

        results = await self.router.dispatch_plan(plan, context_id=context_id)
        await self.runtime.memory.put_working(
            context_id, "results", {k: v.model_dump(mode="json") for k, v in results.items()}
        )

        synthesis = await self.aggregate(objective, plan, results, context_id)

        await self.runtime.memory.episodic.record_run(
            context_id=context_id, objective=objective, result=synthesis
        )
        await self.runtime.observer.record(
            EventType.PIPELINE_COMPLETED,
            source=self.brain_id,
            context_id=context_id,
            message="pipeline complete",
            data={"tasks": len(plan)},
        )

        result = ResultPayload(
            task_id=task.payload.get("task_id", context_id),
            brain_id=self.brain_id,
            status=ResultStatus.SUCCESS,
            summary=synthesis["summary"],
            output=synthesis,
        )
        return task.reply(
            source=self.brain_id,
            message_type=MessageType.RESULT,
            payload=result.model_dump(mode="json"),
        )

    async def decompose(self, objective: str, context_id: str) -> list[TaskPayload]:
        """Decompose an objective into routed tasks.

        Attempts an LLM-produced JSON plan first; if the model does not return a
        usable plan (e.g. the deterministic stub), falls back to a capability
        fan-out across every registered worker brain.

        Args:
            objective: The operator's stated intent.
            context_id: The pipeline run id.

        Returns:
            A list of :class:`TaskPayload`, validated against live capabilities.
        """
        capabilities = await self.runtime.registry.capabilities()
        worker_caps = {
            brain_id: caps for brain_id, caps in capabilities.items() if brain_id != self.brain_id
        }
        if not worker_caps:
            return []

        plan = await self._llm_plan(objective, worker_caps, context_id)
        if plan:
            return plan
        return self._fanout_plan(objective, worker_caps)

    async def _llm_plan(
        self, objective: str, capabilities: dict[str, list[str]], context_id: str
    ) -> list[TaskPayload]:
        """Ask the model for a JSON plan and parse it defensively."""
        response = await self._llm.complete(
            system=CKOS_SYSTEM_PROMPT,
            messages=[
                LLMMessage(
                    role="user",
                    content=build_decomposition_prompt(objective, capabilities),
                )
            ],
        )
        await self.runtime.observer.record(
            EventType.LLM_CALL,
            source=self.brain_id,
            context_id=context_id,
            message="decomposition",
            data=response.usage,
        )
        valid_caps = {cap for caps in capabilities.values() for cap in caps}
        return self._parse_plan(response.content, valid_caps)

    @staticmethod
    def _parse_plan(content: str, valid_caps: set[str]) -> list[TaskPayload]:
        """Extract a JSON task array from model output, dropping invalid tasks."""
        match = re.search(r"\[.*\]", content, re.DOTALL)
        if not match:
            return []
        try:
            raw = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []
        plan: list[TaskPayload] = []
        for item in raw if isinstance(raw, list) else []:
            cap = item.get("capability")
            if cap not in valid_caps:
                continue
            plan.append(
                TaskPayload(
                    task_id=item.get("task_id") or f"task-{len(plan) + 1}",
                    capability=cap,
                    objective=item.get("objective", ""),
                    depends_on=item.get("depends_on", []),
                )
            )
        return plan

    def _fanout_plan(
        self, objective: str, capabilities: dict[str, list[str]]
    ) -> list[TaskPayload]:
        """Deterministic fallback: one task per worker brain's primary capability."""
        plan: list[TaskPayload] = []
        for index, (_brain_id, caps) in enumerate(sorted(capabilities.items()), start=1):
            if not caps:
                continue
            capability = caps[0]
            plan.append(
                TaskPayload(
                    task_id=f"task-{index}-{capability}",
                    capability=capability,
                    objective=f"For the operator's goal '{objective}', "
                    f"apply your '{capability}' capability and report findings.",
                )
            )
        return plan

    async def aggregate(
        self,
        objective: str,
        plan: list[TaskPayload],
        results: dict[str, ResultPayload],
        context_id: str,
    ) -> dict[str, Any]:
        """Synthesize all brain results into one coherent output.

        Args:
            objective: The operator's stated intent.
            plan: The dispatched plan.
            results: Map of ``task_id`` to each brain's result.
            context_id: The pipeline run id.

        Returns:
            A structured synthesis dict including a human-readable ``summary``.
        """
        per_task = []
        for task in plan:
            result = results.get(task.task_id)
            if result is None:
                continue
            per_task.append(
                {
                    "task_id": task.task_id,
                    "capability": task.capability,
                    "brain_id": result.brain_id,
                    "status": result.status.value,
                    "summary": result.summary,
                }
            )

        digest = "\n".join(
            f"- [{row['capability']} via {row['brain_id']}] ({row['status']}): {row['summary']}"
            for row in per_task
        )
        response = await self._llm.complete(
            system=CKOS_SYNTHESIS_PROMPT,
            messages=[
                LLMMessage(
                    role="user",
                    content=f"OPERATOR GOAL:\n{objective}\n\nBRAIN RESULTS:\n{digest}",
                )
            ],
        )
        await self.runtime.observer.record(
            EventType.LLM_CALL,
            source=self.brain_id,
            context_id=context_id,
            message="synthesis",
            data=response.usage,
        )
        failures = [row for row in per_task if row["status"] in ("failed", "blocked")]
        return {
            "summary": response.content,
            "objective": objective,
            "tasks": per_task,
            "completed": len(per_task) - len(failures),
            "failed": len(failures),
        }

    def _escalation(self, task: HarnessMessage, objective: str) -> HarnessMessage:
        """Build a result that escalates to the operator when nothing can run."""
        result = ResultPayload(
            task_id=task.payload.get("task_id", task.context_id),
            brain_id=self.brain_id,
            status=ResultStatus.BLOCKED,
            summary=(
                "No registered worker brains can serve this objective. "
                "Escalating to operator. Objective: " + objective
            ),
            error="no_capable_brains",
        )
        return task.reply(
            source=self.brain_id,
            message_type=MessageType.RESULT,
            payload=result.model_dump(mode="json"),
        )
