"""The pipeline router — the conductor's baton.

The :class:`~harness.core.orchestrator.Orchestrator` decides *what* to do
(decompose an objective into tasks and choose which brain handles each). The
:class:`PipelineRouter` *carries it out*: it dispatches tasks onto the bus,
respects dependencies, collects results, and asks the orchestrator to synthesize
the final output.

Each run gets a unique reply address (``pipeline:<run_id>``) so concurrent runs
never cross wires when collecting results. Every dispatched ``TASK`` message
carries its full ancestry (``objective_id``, ``run_id``, ``task_id``) in
metadata, so any brain can correctly parent a sub-agent it spawns.
"""

from __future__ import annotations

from datetime import UTC, datetime

from harness.core.memory import SharedMemory
from harness.core.message_bus import MessageBus
from harness.core.observer import Observer
from harness.core.orchestrator import Orchestrator
from harness.logging_config import get_logger
from harness.schemas.audit import AuditEventType
from harness.schemas.message import HarnessMessage, MessageType
from harness.schemas.objective import Objective, Run, RunStatus
from harness.schemas.result import Result, ResultStatus
from harness.schemas.task import Task, TaskStatus

logger = get_logger("router")


def reply_address(run_id: str) -> str:
    """Return the unique bus reply address for a run."""
    return f"pipeline:{run_id}"


class PipelineRouter:
    """Dispatches the orchestrator's plan across brains and aggregates results."""

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
            memory: Shared memory for storing run state.
            observer: Observer for pipeline audit events.
            orchestrator: The harness orchestrator (planner/synthesizer).
            result_timeout: Max seconds to wait for each result.
        """
        self._bus = bus
        self._memory = memory
        self._observer = observer
        self._orchestrator = orchestrator
        self._result_timeout = result_timeout

    async def run(self, objective: Objective, *, source: str = "intake") -> Run:
        """Run a full pipeline for an objective: plan, dispatch, collect, synthesize.

        Args:
            objective: The operator's objective.
            source: Who injected the objective (for audit).

        Returns:
            A completed :class:`Run`.
        """
        run = Run(objective_id=objective.objective_id)
        await self._observer.record(
            AuditEventType.PIPELINE_STARTED,
            source=source,
            context_id=run.run_id,
            message=objective.statement[:200],
            data={"objective_id": objective.objective_id},
        )
        await self._memory.remember(run.run_id, "idea", objective.statement)

        tasks = await self._orchestrator.plan(objective, run)
        run.tasks = tasks
        if not tasks:
            run.status = RunStatus.NEEDS_OPERATOR
            run.output = "Orchestrator could not decompose this objective into tasks."
            await self._finish(run, source)
            return run

        await self._memory.remember(
            run.run_id, "plan", [t.model_dump(mode="json") for t in tasks]
        )
        results = await self._execute_waves(tasks, objective, run)
        run.results = results
        run.output = await self._orchestrator.synthesize(objective, run, results)

        if any(r.status == ResultStatus.FAILURE for r in results):
            run.status = RunStatus.PARTIAL
        else:
            run.status = RunStatus.COMPLETED
        await self._finish(run, source)
        return run

    async def _execute_waves(
        self, tasks: list[Task], objective: Objective, run: Run
    ) -> list[Result]:
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

            await self._dispatch_wave(
                [by_id[tid] for tid in ready], completed, objective, run
            )
            collected = await self._collect(len(ready), run)
            for result in collected:
                completed[result.task_id] = result
            remaining -= set(ready)

        return [completed[t.id] for t in tasks if t.id in completed]

    async def _dispatch_wave(
        self, tasks: list[Task], completed: dict[str, Result], objective: Objective, run: Run
    ) -> None:
        """Send each task in a wave to its assigned brain's queue with ancestry."""
        for task in tasks:
            task.status = TaskStatus.RUNNING
            task.run_id = run.run_id
            task.objective_id = objective.objective_id
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
                source=reply_address(run.run_id),
                destination=task.assigned_brain or "harness",
                message_type=MessageType.TASK,
                priority=task.priority,
                payload=task.model_dump(mode="json"),
                context_id=run.run_id,
                metadata={
                    "objective_id": objective.objective_id,
                    "run_id": run.run_id,
                    "task_id": task.id,
                },
            )
            await self._bus.enqueue(message.destination, message)
            await self._bus.mirror_to_observer(message)
            await self._observer.record(
                AuditEventType.MESSAGE_SENT,
                source="harness",
                context_id=run.run_id,
                message=f"TASK -> {message.destination}",
                data={"task_id": task.id, "capability": task.capability},
            )

    async def _collect(self, count: int, run: Run) -> list[Result]:
        """Collect ``count`` results from this run's reply address."""
        address = reply_address(run.run_id)
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
                context_id=run.run_id,
                message=f"RESULT <- {message.source}",
            )
            results.append(Result.model_validate(message.payload))
        return results

    async def _finish(self, run: Run, source: str) -> None:
        """Persist the final output and emit the completion audit event."""
        run.completed_at = datetime.now(UTC)
        await self._memory.remember(run.run_id, "output", run.output)
        await self._memory.remember(run.run_id, "status", run.status.value)
        await self._observer.record(
            AuditEventType.PIPELINE_COMPLETED,
            source=source,
            context_id=run.run_id,
            message=run.output[:200],
            data={"status": run.status.value, "task_count": len(run.tasks)},
        )
