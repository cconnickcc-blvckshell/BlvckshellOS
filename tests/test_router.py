"""Tests for the CKOS router."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from brains.commander import CommanderBrain
from brains.venture import VentureBrain
from harness.core.router import CKOSRouter
from harness.core.runtime import HarnessRuntime, create_runtime
from harness.schemas.result import ResultStatus
from harness.schemas.task import TaskPayload


@pytest.fixture
async def workers() -> AsyncIterator[tuple[HarnessRuntime, CKOSRouter]]:
    rt = create_runtime()
    await rt.start()
    brains = [VentureBrain(rt), CommanderBrain(rt)]
    for brain in brains:
        await brain.start()
    router = CKOSRouter(rt, default_timeout=10.0)
    await router.start()
    try:
        yield rt, router
    finally:
        await router.stop()
        for brain in brains:
            await brain.stop()
        await rt.stop()


async def test_dispatch_task_success(
    workers: tuple[HarnessRuntime, CKOSRouter],
) -> None:
    _, router = workers
    task = TaskPayload(task_id="t1", capability="validate_idea", objective="ship a CLI")
    result = await router.dispatch_task(task, context_id="ctx")
    assert result.status == ResultStatus.SUCCESS
    assert result.brain_id == "venture"


async def test_dispatch_unknown_capability(
    workers: tuple[HarnessRuntime, CKOSRouter],
) -> None:
    _, router = workers
    task = TaskPayload(task_id="t1", capability="time_travel", objective="impossible")
    result = await router.dispatch_task(task, context_id="ctx")
    assert result.status == ResultStatus.FAILED
    assert result.error == "no_capable_brain"


async def test_dispatch_plan_with_dependency(
    workers: tuple[HarnessRuntime, CKOSRouter],
) -> None:
    _, router = workers
    plan = [
        TaskPayload(task_id="a", capability="validate_idea", objective="validate"),
        TaskPayload(
            task_id="b",
            capability="build_execution_plan",
            objective="plan",
            depends_on=["a"],
        ),
    ]
    results = await router.dispatch_plan(plan, context_id="ctx")
    assert results["a"].status == ResultStatus.SUCCESS
    assert results["b"].status == ResultStatus.SUCCESS


async def test_dispatch_plan_dependency_deadlock(
    workers: tuple[HarnessRuntime, CKOSRouter],
) -> None:
    _, router = workers
    plan = [
        TaskPayload(
            task_id="a",
            capability="validate_idea",
            objective="x",
            depends_on=["missing"],
        )
    ]
    results = await router.dispatch_plan(plan, context_id="ctx")
    assert results["a"].status == ResultStatus.BLOCKED
