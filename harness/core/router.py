"""The pipeline router — the conductor's baton.

CKOS is the intelligence that decides *what* to do (decompose an idea into tasks
and choose which brain handles each). The :class:`PipelineRouter` is the
mechanism that *carries it out*: it dispatches tasks onto the bus, respects
dependencies, collects results, and asks CKOS to synthesize the final output.

Each pipeline run gets a unique reply address (``pipeline:<context_id>``) so
concurrent pipelines never cross wires when collecting results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from harness.core.memory import SharedMemory
from harness.core.message_bus import MessageBus
from harness.core.observer import Observer
from harness.logging_config import get_logger
from harness.schemas.audit import AuditEventType
from harness.schemas.message import HarnessMessage, MessageType
from harness.schemas.result import Result, ResultStatus
from harness.schemas.task import Task, TaskStatus

logger = get_logger("router")


class Orchestrator(Protocol):
    """The planning/synthesis contract the router needs from CKOS."""

    async def plan(self, idea: str, context_id: str) -> list[Task]:
        """Decompose an idea into routed, executable tasks."""
        ...

    async def synthesize(self, idea: str, results: list[Result], context_id: str) -> str:
        """Aggregate brain results into a single coherent answer."""
        ...


def reply_address(context_id: str) -> str:
    """Return the unique bus reply address for a pipeline run."""
    return f"pipeline:{context_id}"


@dataclass(slots=True)
class PipelineRun:
    """The outcome of a full pipeline run.

    Attributes:
        context_id: The pipeline run identifier.
        idea: The original operator idea.
        tasks: The tasks CKOS produced.
        results: The results returned by brains.
        output: The synthesized final answer.
        status: Overall pipeline status.
    """

    context_id: str
    idea: str
    tasks: list[Task] = field(default_factory=list)
    results: list[Result] = field(default_factory=list)
    output: str = ""
    status: str = "COMPLETED"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the run."""
        return {
            "context_id": self.context_id,
            "idea": self.idea,
            "status": self.status,
            "output": self.output,
            "tasks": [t.model_dump(mode="json") for t in self.tasks],
            "results": [r.model_dump(mode="json") for r in self.results],
        }


class PipelineRouter:
    """Dispatches CKOS's plan across brains and aggregates the results."""

    def __init__(
        self,
        *,
        bus: MessageBus,
        memory: SharedMemory,
        observer: Observer,
        orchestrator: Orchestrator,
        result_timeout: float = 120.0,
    ) -> None:
        """Create the router.

        Args:
            bus: The message bus for dispatch and collection.
            memory: Shared memory for storing pipeline state.
            observer: Observer for pipeline audit events.
            orchestrator: The CKOS planner/synthesizer.
            result_timeout: Max seconds to wait for each result.
        """
        self._bus = bus
        self._memory = memory
        self._observer = observer
        self._orchestrator = orchestrator
        self._result_timeout = result_timeout

    async def run(self, idea: str, context_id: str, *, source: str = "intake") -> PipelineRun:
        """Run a full pipeline: plan, dispatch, collect, synthesize.

        Args:
            idea: The operator's idea/intent.
            context_id: The pipeline run identifier.
            source: Who injected the idea (for audit).

        Returns:
            A completed :class:`PipelineRun`.
        """
        await self._observer.record(
            AuditEventType.PIPELINE_STARTED,
            source=source,
            context_id=context_id,
            message=idea[:200],
        )
        await self._memory.remember(context_id, "idea", idea)

        tasks = await self._orchestrator.plan(idea, context_id)
        run = PipelineRun(context_id=context_id, idea=idea, tasks=tasks)
        if not tasks:
            run.status = "NEEDS_OPERATOR"
            run.output = "CKOS could not decompose this idea into tasks. Operator input needed."
            await self._finish(run, source)
            return run

        await self._memory.remember(
            context_id, "plan", [t.model_dump(mode="json") for t in tasks]
        )
        results = await self._execute_waves(tasks, context_id)
        run.results = results

        run.output = await self._orchestrator.synthesize(idea, results, context_id)
        if any(r.status == ResultStatus.FAILURE for r in results):
            run.status = "PARTIAL"
        await self._finish(run, source)
        return run

    async def _execute_waves(self, tasks: list[Task], context_id: str) -> list[Result]:
        """Run tasks in dependency-ordered waves, parallelizing each wave."""
        by_id = {t.id: t for t in tasks}
        completed: dict[str, Result] = {}
        remaining = set(by_id)

        while remaining:
            ready = [
                tid
                for tid in remaining
                if all(dep in completed for dep in by_id[tid].depends_on)
            ]
            if not ready:
                # Dependency cycle or unmet dependency: fail the stragglers.
                for tid in remaining:
                    completed[tid] = Result(
                        task_id=tid,
                        brain_id="harness",
                        status=ResultStatus.FAILURE,
                        summary="Unresolvable task dependency.",
                        error="dependency_not_satisfiable",
                    )
                break

            await self._dispatch_wave([by_id[tid] for tid in ready], completed, context_id)
            collected = await self._collect(len(ready), context_id)
            for result in collected:
                completed[result.task_id] = result
            remaining -= set(ready)

        return [completed[t.id] for t in tasks if t.id in completed]

    async def _dispatch_wave(
        self, tasks: list[Task], completed: dict[str, Result], context_id: str
    ) -> None:
        """Send each task in a wave to its assigned brain's queue."""
        for task in tasks:
            task.status = TaskStatus.RUNNING
            # Feed upstream results to dependent tasks as inputs.
            if task.depends_on:
                task.inputs = {
                    **task.inputs,
                    "upstream": {
                        dep: completed[dep].summary
                        for dep in task.depends_on
                        if dep in completed
                    },
                }
            message = HarnessMessage(
                source=reply_address(context_id),
                destination=task.assigned_brain or "harness",
                message_type=MessageType.TASK,
                priority=task.priority,
                payload=task.model_dump(mode="json"),
                context_id=context_id,
            )
            await self._bus.enqueue(message.destination, message)
            await self._bus.mirror_to_observer(message)
            await self._observer.record(
                AuditEventType.MESSAGE_SENT,
                source="harness",
                context_id=context_id,
                message=f"TASK -> {message.destination}",
                data={"task_id": task.id, "capability": task.capability},
            )

    async def _collect(self, count: int, context_id: str) -> list[Result]:
        """Collect ``count`` results from this pipeline's reply address."""
        address = reply_address(context_id)
        results: list[Result] = []
        for _ in range(count):
            message = await self._bus.dequeue(address, timeout=self._result_timeout)
            if message is None:
                results.append(
                    Result(
                        task_id="unknown",
                        brain_id="harness",
                        status=ResultStatus.FAILURE,
                        summary="Timed out waiting for a brain result.",
                        error="result_timeout",
                    )
                )
                continue
            await self._observer.record(
                AuditEventType.MESSAGE_RECEIVED,
                source="harness",
                context_id=context_id,
                message=f"RESULT <- {message.source}",
            )
            results.append(Result.model_validate(message.payload))
        return results

    async def _finish(self, run: PipelineRun, source: str) -> None:
        """Persist the final output and emit the completion audit event."""
        await self._memory.remember(run.context_id, "output", run.output)
        await self._memory.remember(run.context_id, "status", run.status)
        await self._observer.record(
            AuditEventType.PIPELINE_COMPLETED,
            source=source,
            context_id=run.context_id,
            message=run.output[:200],
            data={"status": run.status, "task_count": len(run.tasks)},
        )
