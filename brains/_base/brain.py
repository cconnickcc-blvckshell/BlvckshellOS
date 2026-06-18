"""The plugin contract every brain implements.

A brain is a self-contained specialist. It registers with the harness, listens
on its own queue, and runs the agent loop on each task. The harness handles
transport, discovery, memory, and audit — a new brain only implements three
methods and declares its capabilities.

To add a brain:

1. Extend :class:`BaseBrain` (or :class:`LLMBrain` for the common case).
2. Implement ``handle_task``, ``get_context``, ``log_judgment``.
3. Declare its ``capabilities``.
4. ``docker compose up``.

The harness does the rest.
"""

from __future__ import annotations

import abc
import asyncio
from dataclasses import dataclass

from harness.config import Settings
from harness.core.agent_loop import AgentLoop
from harness.core.llm import LLMClient
from harness.core.memory import SharedMemory
from harness.core.message_bus import MessageBus
from harness.core.observer import Observer
from harness.core.registry import BrainRegistry
from harness.logging_config import get_logger
from harness.schemas.audit import AuditEventType
from harness.schemas.brain_info import BrainContext, BrainInfo, BrainState
from harness.schemas.judgment import JudgmentEntry
from harness.schemas.message import (
    HarnessMessage,
    MessageType,
)
from harness.schemas.objective import AgentCall
from harness.schemas.result import Result, ResultStatus
from harness.schemas.task import Task, TaskStatus
from judgment.lifecycle import JudgmentLifecycle, build_ledger_entry, result_status_for_outcome
from judgment.profile import JudgmentProfile
from judgment.traces import LifecycleRunContext

from brains._base.tools import BaseTool

logger = get_logger("brain")


@dataclass(slots=True)
class BrainRuntime:
    """The harness services injected into every brain.

    Attributes:
        bus: The message bus for task/result transport.
        registry: The brain registry for registration and heartbeats.
        memory: The shared-memory facade.
        observer: The Observer for audit logging.
        llm: The LLM client used by the agent loop.
        settings: Runtime settings.
    """

    bus: MessageBus
    registry: BrainRegistry
    memory: SharedMemory
    observer: Observer
    llm: LLMClient
    settings: Settings


class BaseBrain(abc.ABC):
    """Abstract base every brain extends.

    Subclasses set the class attributes (:attr:`brain_id`, :attr:`name`, etc.)
    and implement the three abstract methods. Lifecycle methods (``register``,
    ``heartbeat``, ``serve``) are provided and should not be overridden.
    """

    brain_id: str = "base"
    name: str = "Base Brain"
    description: str = "Abstract brain."
    capabilities: list[str] = []
    pipeline_participant: bool = True
    model: str = "fake-llm"
    tools: list[BaseTool] = []

    def __init__(self, runtime: BrainRuntime) -> None:
        """Bind the brain to its harness runtime.

        Args:
            runtime: The injected harness services.
        """
        self.runtime = runtime
        self._stopped = asyncio.Event()

    # -- contract ----------------------------------------------------------

    @abc.abstractmethod
    async def handle_task(self, task: HarnessMessage) -> HarnessMessage:
        """Process a task message and return a result message."""

    @abc.abstractmethod
    async def get_context(self, context_id: str) -> BrainContext:
        """Load relevant context for this brain from shared memory."""

    @abc.abstractmethod
    async def log_judgment(self, entry: JudgmentEntry) -> None:
        """Record a decision to the Judgment Ledger."""

    # -- lifecycle (do not override) ---------------------------------------

    def info(self) -> BrainInfo:
        """Return this brain's advertisement record for the registry."""
        return BrainInfo(
            brain_id=self.brain_id,
            name=self.name,
            description=self.description,
            pipeline_participant=self.pipeline_participant,
            capabilities=list(self.capabilities),
            model=self.model,
            tools=[t.name for t in self.tools],
            state=BrainState.IDLE,
        )

    async def register(self) -> None:
        """Register with the harness on startup."""
        await self.runtime.registry.register(self.info())
        await self.runtime.observer.record(
            AuditEventType.BRAIN_REGISTERED,
            source=self.brain_id,
            message=f"{self.name} registered",
            data={"capabilities": self.capabilities, "model": self.model},
        )

    async def deregister(self) -> None:
        """Remove this brain from the registry."""
        await self.runtime.registry.deregister(self.brain_id)
        await self.runtime.observer.record(
            AuditEventType.BRAIN_DEREGISTERED,
            source=self.brain_id,
            message=f"{self.name} deregistered",
        )

    async def heartbeat(self) -> None:
        """Report a single heartbeat to the registry."""
        await self.runtime.registry.heartbeat(self.brain_id)

    async def set_state(self, state: BrainState) -> None:
        """Update this brain's live state (drives the UI status orbs)."""
        await self.runtime.registry.set_state(self.brain_id, state)

    # -- sub-agent spawning (first-class contract) -------------------------

    async def spawn_agent(
        self,
        *,
        capability: str,
        objective: str,
        parent_task_id: str,
        run_id: str,
        objective_id: str,
        inputs: dict | None = None,
        timeout: float = 60.0,
    ) -> AgentCall:
        """Spawn a sub-agent for a capability and await its result.

        The sub-agent is dispatched over the harness bus to whatever brain is
        registered for ``capability`` and runs through the same machinery (bus,
        registry, agent loop, judgment logging). The result is awaited and
        returned as an :class:`AgentCall` with the ``result`` field populated.

        A failed sub-agent (no brain for the capability, or a timeout) returns an
        :class:`AgentCall` with ``status=FAILED`` and ``error`` set — it never
        raises, so it can never crash the parent brain or the harness.

        Args:
            capability: The capability the sub-agent must handle.
            objective: The instruction for the sub-agent.
            parent_task_id: The id of the task spawning this sub-agent.
            run_id: The run this sub-agent belongs to.
            objective_id: The objective this sub-agent serves.
            inputs: Optional structured inputs for the sub-agent.
            timeout: Max seconds to wait for the sub-agent's result.

        Returns:
            The completed :class:`AgentCall`.
        """
        call = AgentCall(
            task_id=parent_task_id,
            run_id=run_id,
            objective_id=objective_id,
            spawned_by=self.brain_id,
            capability=capability,
            objective=objective,
            inputs=inputs or {},
        )
        reply_address = f"agent:{call.agent_call_id}"

        await self.runtime.observer.record(
            AuditEventType.AGENT_SPAWNED,
            source=self.brain_id,
            context_id=run_id,
            message=f"spawned sub-agent for capability '{capability}'",
            data={"agent_call_id": call.agent_call_id, "objective": objective[:120]},
        )

        brain_info = await self.runtime.registry.find_by_capability(capability)
        if brain_info is None:
            call.status = TaskStatus.FAILED
            call.error = f"No brain registered for capability '{capability}'"
            return call

        task = Task(
            run_id=run_id,
            objective_id=objective_id,
            capability=capability,
            objective=objective,
            inputs=inputs or {},
            assigned_brain=brain_info.brain_id,
        )
        task_msg = HarnessMessage(
            source=reply_address,
            destination=brain_info.brain_id,
            message_type=MessageType.TASK,
            payload=task.model_dump(mode="json"),
            context_id=run_id,
            metadata={
                "objective_id": objective_id,
                "run_id": run_id,
                "task_id": task.id,
                "parent_task_id": parent_task_id,
                "agent_call_id": call.agent_call_id,
                "spawned_by": self.brain_id,
            },
        )
        await self.runtime.bus.enqueue(brain_info.brain_id, task_msg)

        result_msg = await self.runtime.bus.dequeue(reply_address, timeout=timeout)
        if result_msg is None:
            call.status = TaskStatus.FAILED
            call.error = f"Sub-agent timed out after {timeout}s"
            return call

        result = Result.model_validate(result_msg.payload)
        call.result = result.summary
        call.error = result.error
        call.status = TaskStatus.COMPLETED if result.succeeded else TaskStatus.FAILED

        await self.runtime.observer.record(
            AuditEventType.AGENT_RETURNED,
            source=self.brain_id,
            context_id=run_id,
            message=f"sub-agent returned for capability '{capability}'",
            data={"agent_call_id": call.agent_call_id, "succeeded": result.succeeded},
        )
        return call

    async def _heartbeat_loop(self) -> None:
        """Emit heartbeats on the configured interval until stopped."""
        interval = self.runtime.settings.heartbeat_interval_seconds
        while not self._stopped.is_set():
            await self.heartbeat()
            try:
                await asyncio.wait_for(self._stopped.wait(), timeout=interval)
            except TimeoutError:
                continue

    async def serve(self) -> None:
        """Register, then process tasks off the bus until stopped.

        This is the brain's main entry point inside its container. A failure on
        any single task is caught and logged — it never stops the brain or the
        harness.
        """
        await self.register()
        heartbeat = asyncio.create_task(self._heartbeat_loop())
        try:
            while not self._stopped.is_set():
                message = await self.runtime.bus.dequeue(self.brain_id, timeout=1.0)
                if message is None:
                    continue
                if message.message_type != MessageType.TASK:
                    continue
                await self._process(message)
        finally:
            heartbeat.cancel()
            await self.set_state(BrainState.OFFLINE)

    async def _process(self, message: HarnessMessage) -> None:
        """Run one task end-to-end with full audit and error isolation."""
        await self.runtime.observer.record(
            AuditEventType.TASK_STARTED,
            source=self.brain_id,
            context_id=message.context_id,
            message=message.payload.get("objective", ""),
            data={"task_id": message.payload.get("id")},
        )
        await self.set_state(BrainState.THINKING)
        try:
            result_message = await self.handle_task(message)
            await self.runtime.bus.enqueue(result_message.destination, result_message)
            await self.runtime.bus.mirror_to_observer(result_message)
            await self.runtime.observer.record(
                AuditEventType.TASK_COMPLETED,
                source=self.brain_id,
                context_id=message.context_id,
                data={"task_id": message.payload.get("id")},
            )
        except Exception as exc:
            logger.error("brain_task_failed", brain=self.brain_id, error=str(exc))
            await self.set_state(BrainState.ERROR)
            await self.runtime.observer.record(
                AuditEventType.TASK_FAILED,
                source=self.brain_id,
                context_id=message.context_id,
                message=str(exc),
                data={"task_id": message.payload.get("id")},
            )
            failure = self._failure_message(message, exc)
            await self.runtime.bus.enqueue(failure.destination, failure)
            await self.runtime.bus.mirror_to_observer(failure)
        finally:
            await self.set_state(BrainState.IDLE)

    def _failure_message(self, task: HarnessMessage, exc: Exception) -> HarnessMessage:
        """Build a RESULT message describing a failed task."""
        result = Result(
            task_id=task.payload.get("id", task.id),
            brain_id=self.brain_id,
            status=ResultStatus.FAILURE,
            summary="Task failed.",
            error=str(exc),
        )
        return task.reply(
            source=self.brain_id,
            message_type=MessageType.RESULT,
            payload=result.model_dump(mode="json"),
        )

    def stop(self) -> None:
        """Signal the serve loop to stop after the current task."""
        self._stopped.set()


class LLMBrain(BaseBrain):
    """A ready-made brain that solves tasks with the LLM agent loop.

    Most specialist brains only need to set their identity, capabilities, and a
    :attr:`system_prompt`. This base wires the agent loop, context loading,
    judgment logging, and result emission.
    """

    system_prompt: str = "You are a specialist brain in the Blvckshell harness."
    max_iterations: int = 6
    judgment_profile: JudgmentProfile = JudgmentProfile()

    async def get_context(self, context_id: str) -> BrainContext:
        """Load this brain's working context from shared memory."""
        return await self.runtime.memory.load_context(context_id, self.brain_id)

    async def log_judgment(self, entry: JudgmentEntry) -> None:
        """Record a belief to the Judgment Ledger via shared memory."""
        await self.runtime.memory.record_judgment(entry)

    def build_user_prompt(self, task: Task, context: BrainContext) -> str:
        """Render the task and relevant context into the first user message.

        Args:
            task: The task to perform.
            context: The loaded working context.

        Returns:
            A prompt string for the agent loop.
        """
        doctrine = "\n".join(f"- {d.belief}" for d in context.doctrine[:5]) or "- (none yet)"
        inputs = task.inputs or {}
        return (
            f"OBJECTIVE:\n{task.objective}\n\n"
            f"INPUTS:\n{inputs}\n\n"
            f"RELEVANT DOCTRINE:\n{doctrine}\n\n"
            "Complete the objective. Be concrete and decisive. End with a clear, "
            "self-contained summary of your conclusion."
        )

    async def handle_task(self, task: HarnessMessage) -> HarnessMessage:
        """Run the judgment lifecycle for a task and emit a structured result."""
        parsed = Task.model_validate(task.payload)
        context = await self.get_context(task.context_id)
        await self.set_state(BrainState.EXECUTING)

        loop = AgentLoop(
            llm=self.runtime.llm,
            tools=self.tools,
            observer=self.runtime.observer,
            max_iterations=self.max_iterations,
        )

        run_context = LifecycleRunContext()

        async def gather_evidence():
            prompt = self.build_user_prompt(parsed, context) + run_context.evidence_prompt_suffix
            return await loop.run(
                brain_id=self.brain_id,
                context_id=task.context_id,
                system_prompt=self.system_prompt,
                user_prompt=prompt,
                model=self.model if self.model != "fake-llm" else None,
            )

        lifecycle = JudgmentLifecycle()
        cycle = await lifecycle.run(
            brain_id=self.brain_id,
            context_id=task.context_id,
            task=parsed,
            context=context,
            profile=self.judgment_profile,
            gather_evidence=gather_evidence,
            observer=self.runtime.observer,
            memory=self.runtime.memory,
            run_context=run_context,
        )

        judgment = build_ledger_entry(
            brain_id=self.brain_id,
            context_id=task.context_id,
            lifecycle=cycle,
        )
        await self.log_judgment(judgment)

        result = Result(
            task_id=parsed.id,
            brain_id=self.brain_id,
            status=result_status_for_outcome(cycle.outcome),
            output={"analysis": cycle.raw_analysis, "judgment_outcome": cycle.outcome.value},
            summary=cycle.belief[:280],
            judgment_ids=[judgment.id],
            judgment_outcome=cycle.outcome,
            stage_trace_id=cycle.trace_id,
            metrics=cycle.agent_metrics,
        )
        await self.runtime.memory.append_working(
            task.context_id,
            "history",
            {
                "brain": self.brain_id,
                "summary": result.summary,
                "judgment_outcome": cycle.outcome.value,
            },
        )
        return task.reply(
            source=self.brain_id,
            message_type=MessageType.RESULT,
            payload=result.model_dump(mode="json"),
            metadata=cycle.agent_metrics,
        )
