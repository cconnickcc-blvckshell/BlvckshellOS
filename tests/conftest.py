"""Shared pytest fixtures for the harness test suite.

All fixtures run against the zero-dependency in-process backends (in-memory bus,
in-memory persistence, deterministic stub LLM), so the full suite runs anywhere.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from harness.bootstrap import default_brains, start_brains, stop_brains
from harness.core.runtime import HarnessRuntime, create_runtime
from intake.service import IntakeService


@pytest.fixture
async def runtime() -> AsyncIterator[HarnessRuntime]:
    """Provide a started, isolated harness runtime."""
    rt = create_runtime()
    await rt.start()
    try:
        yield rt
    finally:
        await rt.stop()


@pytest.fixture
async def running_harness(
    runtime: HarnessRuntime,
) -> AsyncIterator[tuple[HarnessRuntime, IntakeService]]:
    """Provide a runtime with the full brain federation and intake started."""
    brains = default_brains(runtime)
    await start_brains(brains)
    intake = IntakeService(runtime)
    await intake.start()
    try:
        yield runtime, intake
    finally:
        await intake.stop()
        await stop_brains(brains)
