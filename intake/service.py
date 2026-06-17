"""IntakeService — funnels normalized objectives into CKOS and tracks pipelines.

The operator drops an idea; the service immediately returns a pipeline id and
fires the objective at CKOS as a TASK. Results returning on the ``intake``
channel are correlated by ``context_id`` so callers can await or poll them.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

from harness.core.logging import get_logger
from harness.core.runtime import HarnessRuntime
from harness.schemas.event import EventType
from harness.schemas.message import INTAKE_ADDRESS, HarnessMessage, MessageType
from harness.schemas.result import ResultPayload
from harness.schemas.task import TaskPayload

logger = get_logger(__name__)

CKOS_ADDRESS = "ckos"


class IntakeService:
    """Captures objectives and tracks their pipelines end to end."""

    def __init__(self, runtime: HarnessRuntime) -> None:
        """Bind the service to the runtime; correlation starts in ``start``."""
        self._runtime = runtime
        self._pending: dict[str, asyncio.Future[ResultPayload]] = {}
        self._completed: dict[str, ResultPayload] = {}
        self._started = False

    async def start(self) -> None:
        """Subscribe to the intake channel to receive final pipeline results."""
        if self._started:
            return
        await self._runtime.bus.subscribe(INTAKE_ADDRESS, self._on_result)
        self._started = True

    async def stop(self) -> None:
        """Unsubscribe from the intake channel."""
        if not self._started:
            return
        await self._runtime.bus.unsubscribe(INTAKE_ADDRESS, self._on_result)
        self._started = False

    async def _on_result(self, message: HarnessMessage) -> None:
        """Correlate a returning CKOS result with its pipeline id."""
        if message.message_type != MessageType.RESULT:
            return
        await self._runtime.observer.record_message(message, direction="received")
        result = ResultPayload.model_validate(message.payload)
        self._completed[message.context_id] = result
        future = self._pending.get(message.context_id)
        if future is not None and not future.done():
            future.set_result(result)

    async def submit(self, objective: str, *, priority: int = 4) -> str:
        """Submit a normalized objective to CKOS and return the pipeline id.

        Args:
            objective: The normalized operator objective.
            priority: Message priority (1-5).

        Returns:
            The ``context_id`` that identifies this pipeline run.
        """
        await self.start()
        context_id = str(uuid4())
        loop = asyncio.get_running_loop()
        self._pending[context_id] = loop.create_future()

        task = TaskPayload(
            task_id=context_id,
            capability="orchestrate",
            objective=objective,
        )
        message = HarnessMessage(
            source=INTAKE_ADDRESS,
            destination=CKOS_ADDRESS,
            message_type=MessageType.TASK,
            priority=priority,
            payload=task.model_dump(mode="json"),
            context_id=context_id,
        )
        await self._runtime.observer.record(
            EventType.PIPELINE_STARTED,
            source=INTAKE_ADDRESS,
            context_id=context_id,
            message=objective[:160],
        )
        await self._runtime.observer.record_message(message, direction="sent")
        await self._runtime.bus.publish(message)
        return context_id

    async def await_result(
        self, context_id: str, *, timeout: float = 120.0
    ) -> ResultPayload | None:
        """Await the final aggregated result for a pipeline.

        Args:
            context_id: The pipeline id returned by :meth:`submit`.
            timeout: How long to wait before giving up.

        Returns:
            The :class:`ResultPayload`, or ``None`` on timeout/unknown id.
        """
        if context_id in self._completed:
            return self._completed[context_id]
        future = self._pending.get(context_id)
        if future is None:
            return None
        try:
            return await asyncio.wait_for(asyncio.shield(future), timeout)
        except TimeoutError:
            return None

    def result_for(self, context_id: str) -> ResultPayload | None:
        """Return an already-completed result without awaiting, if present."""
        return self._completed.get(context_id)
