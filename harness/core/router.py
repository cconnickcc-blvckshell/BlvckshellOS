"""CKOS routing logic — dispatch tasks to brains and collect their results.

The router is the mechanical half of orchestration: given a set of decomposed
tasks (produced by CKOS), it resolves each to a healthy brain by capability,
publishes the TASK on the bus, and correlates the returning RESULT messages —
running independent tasks in parallel and respecting declared dependencies.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from harness.core.logging import get_logger
from harness.schemas.message import HARNESS_ADDRESS, HarnessMessage, MessageType
from harness.schemas.result import ResultPayload, ResultStatus
from harness.schemas.task import TaskPayload

if TYPE_CHECKING:  # pragma: no cover - typing only
    from harness.core.runtime import HarnessRuntime

logger = get_logger(__name__)


class CKOSRouter:
    """Resolves tasks to brains and collects their results over the bus."""

    def __init__(self, runtime: HarnessRuntime, *, default_timeout: float = 60.0) -> None:
        """Bind the router to the runtime and set a default result timeout."""
        self._runtime = runtime
        self._default_timeout = default_timeout
        self._pending: dict[str, asyncio.Future[ResultPayload]] = {}
        self._started = False

    async def start(self) -> None:
        """Subscribe to the harness address to correlate incoming results."""
        if self._started:
            return
        await self._runtime.bus.subscribe(HARNESS_ADDRESS, self._on_result)
        self._started = True

    async def stop(self) -> None:
        """Unsubscribe the result correlator."""
        if not self._started:
            return
        await self._runtime.bus.unsubscribe(HARNESS_ADDRESS, self._on_result)
        self._started = False

    async def _on_result(self, message: HarnessMessage) -> None:
        """Resolve the pending future that matches a returning RESULT message."""
        if message.message_type != MessageType.RESULT:
            return
        task_id = message.payload.get("task_id")
        future = self._pending.get(task_id)
        if future is not None and not future.done():
            future.set_result(ResultPayload.model_validate(message.payload))

    async def resolve_brain(self, capability: str) -> str | None:
        """Return the best healthy ``brain_id`` for a capability, or ``None``.

        Args:
            capability: The required capability.

        Returns:
            A ``brain_id``, or ``None`` if no healthy brain advertises it.
        """
        candidates = await self._runtime.registry.find_by_capability(capability)
        return candidates[0].brain_id if candidates else None

    async def dispatch_task(
        self,
        task: TaskPayload,
        *,
        context_id: str,
        timeout: float | None = None,
    ) -> ResultPayload:
        """Route a single task to a brain and await its result.

        Args:
            task: The task to dispatch.
            context_id: The pipeline run id.
            timeout: Optional override for how long to await a result.

        Returns:
            The brain's :class:`ResultPayload`. A synthetic ``FAILED`` result is
            returned if no brain matches or the brain does not respond in time.
        """
        await self.start()
        brain_id = await self.resolve_brain(task.capability)
        if brain_id is None:
            return ResultPayload(
                task_id=task.task_id,
                brain_id="harness",
                status=ResultStatus.FAILED,
                summary=f"No registered brain advertises capability '{task.capability}'",
                error="no_capable_brain",
            )

        task.assigned_brain = brain_id
        loop = asyncio.get_running_loop()
        future: asyncio.Future[ResultPayload] = loop.create_future()
        self._pending[task.task_id] = future

        message = HarnessMessage(
            source=HARNESS_ADDRESS,
            destination=brain_id,
            message_type=MessageType.TASK,
            priority=4,
            payload=task.model_dump(mode="json"),
            context_id=context_id,
            metadata={"capability": task.capability},
        )
        await self._runtime.observer.record_message(message, direction="sent")
        await self._runtime.bus.publish(message)

        try:
            return await asyncio.wait_for(future, timeout or self._default_timeout)
        except TimeoutError:
            return ResultPayload(
                task_id=task.task_id,
                brain_id=brain_id,
                status=ResultStatus.FAILED,
                summary=f"Brain '{brain_id}' timed out on task '{task.task_id}'",
                error="timeout",
            )
        finally:
            self._pending.pop(task.task_id, None)

    async def dispatch_plan(
        self,
        tasks: list[TaskPayload],
        *,
        context_id: str,
        timeout: float | None = None,
    ) -> dict[str, ResultPayload]:
        """Dispatch a dependency-ordered plan, parallelizing where possible.

        Tasks with satisfied dependencies run concurrently. Dependent tasks wait
        for their prerequisites. The method always terminates: any task whose
        dependencies can never be satisfied is failed deterministically.

        Args:
            tasks: The decomposed plan.
            context_id: The pipeline run id.
            timeout: Optional per-task result timeout.

        Returns:
            A mapping of ``task_id`` to its :class:`ResultPayload`.
        """
        await self.start()
        remaining = {task.task_id: task for task in tasks}
        results: dict[str, ResultPayload] = {}

        while remaining:
            ready = [
                task
                for task in remaining.values()
                if all(dep in results for dep in task.depends_on)
            ]
            if not ready:
                for task in remaining.values():
                    results[task.task_id] = ResultPayload(
                        task_id=task.task_id,
                        brain_id="harness",
                        status=ResultStatus.BLOCKED,
                        summary="Unsatisfiable dependencies; task could not run",
                        error="dependency_deadlock",
                    )
                break

            dispatched = await asyncio.gather(
                *(
                    self.dispatch_task(task, context_id=context_id, timeout=timeout)
                    for task in ready
                )
            )
            for task, result in zip(ready, dispatched, strict=True):
                results[task.task_id] = result
                remaining.pop(task.task_id, None)

        return results
