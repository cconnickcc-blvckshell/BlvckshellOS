"""BaseBrain — the plugin contract that makes brains plug-and-play.

A new brain is created by extending :class:`BaseBrain`, implementing
``handle_task``, ``get_context`` and ``log_judgment``, declaring its
capabilities, and starting it. The harness handles registration, message
delivery, heartbeats, agent looping and auditing.
"""

from __future__ import annotations

import abc
import asyncio
from contextlib import suppress

from harness.config import settings
from harness.core.agent_loop import AgentLoop, AgentLoopResult
from harness.core.inference import LLMClient
from harness.core.logging import get_logger
from harness.core.runtime import HarnessRuntime
from harness.schemas.brain import BrainContext, BrainInfo, BrainStatus
from harness.schemas.event import EventType
from harness.schemas.judgment import JudgmentEntry
from harness.schemas.message import HarnessMessage, MessageType
from harness.schemas.result import ResultPayload, ResultStatus

from brains._base.tools import BaseTool

logger = get_logger(__name__)


class BaseBrain(abc.ABC):
    """Abstract base every specialized brain extends."""

    brain_id: str = "base"
    name: str = "Base Brain"
    description: str = "Abstract base brain."
    capabilities: list[str] = []
    model: str = "stub-1"

    def __init__(self, runtime: HarnessRuntime, *, tools: list[BaseTool] | None = None) -> None:
        """Bind the brain to the shared runtime.

        Args:
            runtime: The wired harness runtime (bus, registry, memory, observer).
            tools: Optional tools this brain may call during its agent loop.
        """
        self.runtime = runtime
        self.tools: list[BaseTool] = tools or []
        self._llm: LLMClient = runtime.llm_factory(self.model)
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._running = False

    # ------------------------------------------------------------------ #
    # Abstract contract — every brain MUST implement these three.
    # ------------------------------------------------------------------ #
    @abc.abstractmethod
    async def handle_task(self, task: HarnessMessage) -> HarnessMessage:
        """Process a task message and return a result message.

        Args:
            task: A ``TASK`` :class:`HarnessMessage`.

        Returns:
            A ``RESULT`` :class:`HarnessMessage` addressed back to the sender.
        """

    @abc.abstractmethod
    async def get_context(self, context_id: str) -> BrainContext:
        """Load relevant context for this brain from shared memory.

        Args:
            context_id: The pipeline run to load context for.

        Returns:
            A populated :class:`BrainContext`.
        """

    @abc.abstractmethod
    async def log_judgment(self, entry: JudgmentEntry) -> None:
        """Record a decision to the Judgment Ledger.

        Args:
            entry: The belief to record.
        """

    # ------------------------------------------------------------------ #
    # Concrete helpers brains can reuse for the abstract methods above.
    # ------------------------------------------------------------------ #
    async def default_context(self, context_id: str) -> BrainContext:
        """Assemble context via the shared memory facade (sensible default)."""
        return await self.runtime.memory.assemble_context(
            context_id=context_id, brain_id=self.brain_id
        )

    async def default_log_judgment(self, entry: JudgmentEntry) -> JudgmentEntry:
        """Record a judgment and emit the corresponding observer event."""
        recorded = await self.runtime.memory.log_judgment(entry)
        await self.runtime.observer.record(
            EventType.JUDGMENT_CREATED,
            source=self.brain_id,
            context_id=entry.context_id,
            message=entry.belief[:120],
            data={"confidence": entry.confidence, "judgment_id": entry.id},
        )
        return recorded

    # ------------------------------------------------------------------ #
    # Lifecycle — DO NOT override register/heartbeat.
    # ------------------------------------------------------------------ #
    @property
    def info(self) -> BrainInfo:
        """Return this brain's current advertisement for the registry."""
        return BrainInfo(
            brain_id=self.brain_id,
            name=self.name,
            description=self.description,
            capabilities=list(self.capabilities),
            model=self.model,
        )

    async def register(self) -> None:
        """Register with the harness on startup. Do not override."""
        await self.runtime.registry.register(self.info)

    async def heartbeat(self) -> None:
        """Send a single heartbeat to the registry. Do not override."""
        await self.runtime.registry.heartbeat(self.brain_id)
        await self.runtime.observer.record(
            EventType.BRAIN_HEARTBEAT, source=self.brain_id, message="heartbeat"
        )

    async def start(self) -> None:
        """Register, subscribe to the bus, and begin heartbeating."""
        await self.register()
        await self.runtime.bus.subscribe(self.brain_id, self._on_message)
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("Brain '%s' started", self.brain_id)

    async def stop(self) -> None:
        """Stop heartbeating and unsubscribe from the bus."""
        self._running = False
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._heartbeat_task
        await self.runtime.bus.unsubscribe(self.brain_id, self._on_message)
        await self.runtime.registry.set_status(self.brain_id, BrainStatus.OFFLINE)

    async def _heartbeat_loop(self) -> None:
        """Periodically heartbeat while the brain is running."""
        while self._running:
            with suppress(Exception):
                await self.heartbeat()
            await asyncio.sleep(settings.heartbeat_interval_seconds)

    async def _on_message(self, message: HarnessMessage) -> None:
        """Bus entry point: dispatch tasks, ignore everything else.

        A failure here never propagates: it is caught, logged, audited and
        returned to the sender as a failed result so the harness stays alive.
        """
        if message.message_type != MessageType.TASK:
            return
        await self.runtime.registry.set_status(
            self.brain_id, BrainStatus.THINKING, task_id=message.payload.get("task_id")
        )
        await self.runtime.observer.record(
            EventType.TASK_STARTED,
            source=self.brain_id,
            context_id=message.context_id,
            message=message.payload.get("objective", "")[:120],
            data={"task_id": message.payload.get("task_id")},
        )
        try:
            result = await self.handle_task(message)
            await self.runtime.bus.publish(result)
            await self.runtime.observer.record(
                EventType.TASK_COMPLETED,
                source=self.brain_id,
                context_id=message.context_id,
                message="task completed",
                data={"task_id": message.payload.get("task_id")},
            )
            await self.runtime.registry.set_status(self.brain_id, BrainStatus.IDLE)
        except Exception as exc:  # noqa: BLE001 - a brain failure must not crash the harness
            logger.exception("Brain '%s' failed handling task", self.brain_id)
            await self.runtime.registry.set_status(self.brain_id, BrainStatus.ERROR)
            await self.runtime.observer.record(
                EventType.TASK_FAILED,
                source=self.brain_id,
                context_id=message.context_id,
                message=str(exc),
                data={"task_id": message.payload.get("task_id")},
            )
            failure = ResultPayload(
                task_id=message.payload.get("task_id", "unknown"),
                brain_id=self.brain_id,
                status=ResultStatus.FAILED,
                summary=f"{self.name} failed: {exc}",
                error=str(exc),
            )
            await self.runtime.bus.publish(
                message.reply(
                    source=self.brain_id,
                    message_type=MessageType.RESULT,
                    payload=failure.model_dump(mode="json"),
                )
            )

    # ------------------------------------------------------------------ #
    # The agent loop — think / act / observe / iterate.
    # ------------------------------------------------------------------ #
    def system_prompt(self) -> str:
        """Return the system prompt establishing this brain's role.

        Override to customize. The default identifies the brain and its remit.
        """
        return (
            f"{self.name} ({self.brain_id}).\n"
            f"Role: {self.description}\n"
            f"Capabilities: {', '.join(self.capabilities)}.\n"
            "Be precise. Prefer explicit, verifiable reasoning over speculation."
        )

    async def think(
        self,
        *,
        objective: str,
        context: BrainContext,
        max_iterations: int | None = None,
    ) -> AgentLoopResult:
        """Run the THINK/ACT/OBSERVE loop until the task is resolved.

        Delegates to the shared :class:`AgentLoop` engine so every brain runs an
        identical, audited loop.

        Args:
            objective: The natural-language objective for this task.
            context: The loaded :class:`BrainContext`.
            max_iterations: Optional override for the iteration cap.

        Returns:
            An :class:`AgentLoopResult` with final content, tool trace and usage.
        """
        loop = AgentLoop(
            brain_id=self.brain_id,
            system_prompt=self.system_prompt(),
            llm=self._llm,
            tools=self.tools,
            observer=self.runtime.observer,
            registry=self.runtime.registry,
        )
        return await loop.run(
            objective=objective, context=context, max_iterations=max_iterations
        )
