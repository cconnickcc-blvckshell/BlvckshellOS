"""Inspect or manually register brains against the live registry.

Primarily a diagnostic: list registered brains, or push a one-off registration
record (useful when bringing up an external brain that has not started its own
serve loop yet).

Usage:
    python -m scripts.register_brain list
    python -m scripts.register_brain show <brain_id>
"""

from __future__ import annotations

import asyncio
import sys

from harness.config import get_settings
from harness.core.registry import build_registry


async def _list() -> None:
    """Print every registered brain and its capabilities/state."""
    settings = get_settings()
    registry = build_registry(
        redis_url=settings.redis_url, use_in_memory=settings.use_in_memory_bus
    )
    await registry.connect()
    try:
        brains = await registry.list_all()
        if not brains:
            print("no brains registered")
        for brain in brains:
            print(f"{brain.brain_id:12} [{brain.state.value:9}] {brain.capabilities}")
    finally:
        await registry.close()


async def _show(brain_id: str) -> None:
    """Print a single brain's full registration record as JSON."""
    settings = get_settings()
    registry = build_registry(
        redis_url=settings.redis_url, use_in_memory=settings.use_in_memory_bus
    )
    await registry.connect()
    try:
        info = await registry.get(brain_id)
        print(info.model_dump_json(indent=2) if info else f"'{brain_id}' not registered")
    finally:
        await registry.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "list":
        asyncio.run(_list())
    elif args[0] == "show" and len(args) > 1:
        asyncio.run(_show(args[1]))
    else:
        raise SystemExit("usage: python -m scripts.register_brain [list | show <brain_id>]")
