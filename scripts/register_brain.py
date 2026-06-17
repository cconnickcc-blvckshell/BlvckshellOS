"""Run and register a single brain as a standalone process.

Connects the brain to the shared message bus and memory, registers it with the
harness, and keeps it alive heartbeating until interrupted. This is the entry
point used by ``docker/Dockerfile.brain`` to run one brain per container.

Usage:
    python -m scripts.register_brain <brain_id>
    python -m scripts.register_brain --list
"""

from __future__ import annotations

import asyncio
import signal
import sys

from brains.catalog import BRAIN_CLASSES, get_brain_class
from harness.core.logging import get_logger
from harness.core.runtime import create_runtime

logger = get_logger(__name__)


async def _run(brain_id: str) -> None:
    """Start the named brain and block until a shutdown signal arrives."""
    runtime = create_runtime()
    await runtime.start()
    brain = get_brain_class(brain_id)(runtime)
    await brain.start()
    logger.info("Brain '%s' is live and registered. Press Ctrl+C to stop.", brain_id)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # pragma: no cover - Windows
            pass

    try:
        await stop.wait()
    finally:
        await brain.stop()
        await runtime.stop()
        logger.info("Brain '%s' stopped.", brain_id)


def main() -> None:
    """CLI entry point: parse the brain id (or --list) and run it."""
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print("usage: python -m scripts.register_brain <brain_id> | --list", file=sys.stderr)
        raise SystemExit(2)
    if args[0] == "--list":
        for brain_id, cls in sorted(BRAIN_CLASSES.items()):
            print(f"{brain_id:12s} {cls.name} — {', '.join(cls.capabilities)}")
        return
    asyncio.run(_run(args[0]))


if __name__ == "__main__":
    main()
