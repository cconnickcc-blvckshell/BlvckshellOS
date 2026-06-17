"""Bootstrap helpers — assemble and start the default brain federation."""

from __future__ import annotations

from brains._base.brain import BaseBrain
from brains.capital import CapitalBrain
from brains.ckos import CKOSBrain
from brains.commander import CommanderBrain
from brains.venture import VentureBrain

from harness.core.logging import get_logger
from harness.core.runtime import HarnessRuntime, create_runtime

logger = get_logger(__name__)


def default_brains(runtime: HarnessRuntime) -> list[BaseBrain]:
    """Instantiate the default federation of brains against a runtime.

    Args:
        runtime: The wired harness runtime.

    Returns:
        The default brains: CKOS plus Venture, Commander and Capital (stub).
    """
    return [
        CKOSBrain(runtime),
        VentureBrain(runtime),
        CommanderBrain(runtime),
        CapitalBrain(runtime),
    ]


async def start_brains(brains: list[BaseBrain]) -> None:
    """Start every brain (register, subscribe, heartbeat)."""
    for brain in brains:
        await brain.start()


async def stop_brains(brains: list[BaseBrain]) -> None:
    """Stop every brain cleanly."""
    for brain in brains:
        await brain.stop()


async def build_running_harness() -> tuple[HarnessRuntime, list[BaseBrain]]:
    """Create a runtime, start it, and start the default brain federation.

    Returns:
        A tuple of the running runtime and the started brains.
    """
    runtime = create_runtime()
    await runtime.start()
    brains = default_brains(runtime)
    await start_brains(brains)
    logger.info("Harness running with %d brains", len(brains))
    return runtime, brains
