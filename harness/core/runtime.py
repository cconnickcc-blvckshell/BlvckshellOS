"""The harness runtime — a single wired-together bundle of core subsystems.

Brains and the API receive a :class:`HarnessRuntime` so every component shares
the same message bus, registry, memory and observer instances.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from harness.core.inference import LLMClient, create_llm_client
from harness.core.memory import SharedMemory
from harness.core.message_bus import MessageBus, create_message_bus
from harness.core.observer import Observer
from harness.core.registry import BrainRegistry


@dataclass
class HarnessRuntime:
    """Container for the shared core subsystems of a running harness.

    Attributes:
        bus: The message bus all brains communicate through.
        registry: The brain registry.
        memory: The shared memory facade.
        observer: The audit log.
        llm_factory: Factory producing an :class:`LLMClient` for a given model.
    """

    bus: MessageBus
    registry: BrainRegistry
    memory: SharedMemory
    observer: Observer
    llm_factory: Callable[[str | None], LLMClient]

    async def start(self) -> None:
        """Connect the message bus and ready the runtime."""
        await self.bus.connect()

    async def stop(self) -> None:
        """Disconnect the message bus and release resources."""
        await self.bus.disconnect()


def create_runtime() -> HarnessRuntime:
    """Build a fully-wired runtime from configuration.

    Returns:
        A :class:`HarnessRuntime` with subsystems sharing one observer.
    """
    observer = Observer()
    return HarnessRuntime(
        bus=create_message_bus(),
        registry=BrainRegistry(observer=observer),
        memory=SharedMemory(),
        observer=observer,
        llm_factory=create_llm_client,
    )
