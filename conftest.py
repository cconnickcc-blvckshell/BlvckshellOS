"""Shared pytest fixtures for the Blvckshell harness test suite.

All fixtures run the harness fully offline: the in-memory bus/memory/registry
backends and the deterministic fake LLM. No Redis, Supabase, or API keys needed.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from harness.config import Settings
from harness.core.harness import Harness


@pytest.fixture
def offline_settings() -> Settings:
    """Return settings that force fully offline, deterministic operation."""
    return Settings(
        environment="test",
        use_in_memory_bus=True,
        use_fake_llm=True,
        heartbeat_interval_seconds=1,
        log_level="WARNING",
    )


@pytest.fixture
async def harness(offline_settings: Settings) -> AsyncIterator[Harness]:
    """Provide a started harness, torn down after the test."""
    instance = Harness(offline_settings)
    await instance.startup()
    try:
        yield instance
    finally:
        await instance.shutdown()
