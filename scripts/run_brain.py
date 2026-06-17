"""Run a single brain in its own process/container.

This is the entry point for the distributed deployment pattern: each brain runs
in its own container, connects to the shared Redis bus + registry, and serves
tasks. Set ``BLVCKSHELL_RUN_WORKERS_IN_PROCESS=false`` on the harness so it does
not also run these brains in-process.

Usage:
    python -m scripts.run_brain venture
"""

from __future__ import annotations

import asyncio
import sys

from brains._base.brain import BaseBrain, BrainRuntime
from brains.examples.capital import CapitalBrain
from brains.examples.commander import CommanderBrain
from brains.examples.venture import VentureBrain
from harness.config import get_settings
from harness.core.llm import build_llm_client
from harness.core.memory import build_shared_memory
from harness.core.message_bus import build_message_bus
from harness.core.observer import (
    InMemoryAuditStore,
    Observer,
    SupabaseAuditStore,
)
from harness.core.registry import build_registry
from harness.logging_config import configure_logging, get_logger

logger = get_logger("run_brain")

BRAINS: dict[str, type[BaseBrain]] = {
    "venture": VentureBrain,
    "commander": CommanderBrain,
    "capital": CapitalBrain,
}


async def main(brain_id: str) -> None:
    """Build the runtime and serve the requested brain until interrupted.

    Args:
        brain_id: The id of the brain to run (a key of :data:`BRAINS`).
    """
    settings = get_settings()
    configure_logging(settings.log_level)

    brain_cls = BRAINS.get(brain_id)
    if brain_cls is None:
        raise SystemExit(f"unknown brain '{brain_id}'. Options: {', '.join(BRAINS)}")

    observer = Observer(
        SupabaseAuditStore(settings.supabase_url, settings.supabase_key)
        if settings.supabase_enabled
        else InMemoryAuditStore()
    )
    bus = build_message_bus(
        redis_url=settings.redis_url, use_in_memory=settings.use_in_memory_bus
    )
    registry = build_registry(
        redis_url=settings.redis_url, use_in_memory=settings.use_in_memory_bus
    )
    memory = build_shared_memory(settings, observer)

    await observer.connect()
    await bus.connect()
    await registry.connect()
    await memory.connect()

    runtime = BrainRuntime(
        bus=bus,
        registry=registry,
        memory=memory,
        observer=observer,
        llm=build_llm_client(settings),
        settings=settings,
    )
    brain = brain_cls(runtime)
    logger.info("brain_starting", brain=brain.brain_id)
    try:
        await brain.serve()
    finally:
        await memory.close()
        await registry.close()
        await bus.close()
        await observer.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: python -m scripts.run_brain <brain_id>")
    asyncio.run(main(sys.argv[1]))
