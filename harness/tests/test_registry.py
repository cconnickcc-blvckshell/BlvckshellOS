"""Tests for the in-memory brain registry."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from harness.core.registry import InMemoryBrainRegistry
from harness.schemas.brain_info import BrainInfo, BrainState


def _info(brain_id: str, caps: list[str]) -> BrainInfo:
    return BrainInfo(brain_id=brain_id, name=brain_id, description="d", capabilities=caps)


async def test_register_and_get() -> None:
    reg = InMemoryBrainRegistry()
    await reg.register(_info("venture", ["idea_validation"]))
    found = await reg.get("venture")
    assert found is not None
    assert found.handles("idea_validation")


async def test_find_by_capability() -> None:
    reg = InMemoryBrainRegistry()
    await reg.register(_info("venture", ["idea_validation"]))
    await reg.register(_info("commander", ["execution_planning"]))
    matches = await reg.find_by_capability("execution_planning")
    assert [m.brain_id for m in matches] == ["commander"]


async def test_heartbeat_and_state() -> None:
    reg = InMemoryBrainRegistry()
    await reg.register(_info("venture", ["x"]))
    updated = await reg.heartbeat("venture", state=BrainState.THINKING)
    assert updated is not None
    assert updated.state == BrainState.THINKING
    await reg.set_state("venture", BrainState.EXECUTING)
    assert (await reg.get("venture")).state == BrainState.EXECUTING


async def test_deregister() -> None:
    reg = InMemoryBrainRegistry()
    await reg.register(_info("venture", ["x"]))
    await reg.deregister("venture")
    assert await reg.get("venture") is None


async def test_stale_detection() -> None:
    reg = InMemoryBrainRegistry()
    info = _info("venture", ["x"])
    info.last_heartbeat = datetime.now(UTC) - timedelta(seconds=120)
    await reg.register(info)
    stale = await reg.stale_brains(timeout_seconds=45)
    assert [s.brain_id for s in stale] == ["venture"]
