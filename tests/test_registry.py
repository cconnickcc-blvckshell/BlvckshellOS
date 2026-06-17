"""Tests for the brain registry."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from harness.core.observer import Observer
from harness.core.registry import BrainRegistry
from harness.schemas.brain import BrainInfo, BrainStatus


def _info(brain_id: str, caps: list[str]) -> BrainInfo:
    return BrainInfo(
        brain_id=brain_id,
        name=brain_id.title(),
        description="test brain",
        capabilities=caps,
        model="stub-1",
    )


async def test_register_and_lookup() -> None:
    reg = BrainRegistry(observer=Observer())
    await reg.register(_info("venture", ["validate_idea"]))
    assert (await reg.get("venture")).name == "Venture"
    assert len(await reg.all()) == 1


async def test_find_by_capability() -> None:
    reg = BrainRegistry()
    await reg.register(_info("venture", ["validate_idea"]))
    await reg.register(_info("commander", ["build_execution_plan"]))
    found = await reg.find_by_capability("validate_idea")
    assert [b.brain_id for b in found] == ["venture"]
    assert await reg.find_by_capability("nonexistent") == []


async def test_capabilities_map() -> None:
    reg = BrainRegistry()
    await reg.register(_info("venture", ["validate_idea", "assess_feasibility"]))
    caps = await reg.capabilities()
    assert caps["venture"] == ["validate_idea", "assess_feasibility"]


async def test_stale_brain_is_pruned_and_unhealthy() -> None:
    reg = BrainRegistry()
    await reg.register(_info("venture", ["validate_idea"]))
    info = await reg.get("venture")
    info.last_heartbeat = datetime.now(UTC) - timedelta(hours=1)
    pruned = await reg.prune_stale()
    assert "venture" in pruned
    assert (await reg.get("venture")).status == BrainStatus.OFFLINE
    # An offline/stale brain must not be routable.
    assert await reg.find_by_capability("validate_idea") == []


async def test_set_status_and_heartbeat() -> None:
    reg = BrainRegistry()
    await reg.register(_info("venture", ["validate_idea"]))
    await reg.set_status("venture", BrainStatus.THINKING, task_id="t1")
    info = await reg.get("venture")
    assert info.status == BrainStatus.THINKING
    assert info.current_task_id == "t1"
    await reg.heartbeat("venture", BrainStatus.IDLE)
    assert (await reg.get("venture")).status == BrainStatus.IDLE
