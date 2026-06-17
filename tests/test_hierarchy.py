"""Tests for the Objective -> Run -> Task ancestry (Change 1)."""

from __future__ import annotations

from harness.core.harness import Harness
from harness.schemas.objective import AgentCall, Objective, Run, RunStatus
from harness.schemas.task import Task, TaskStatus


def test_objective_run_task_schema_relationships() -> None:
    objective = Objective(statement="do the thing")
    run = Run(objective_id=objective.objective_id)
    assert run.objective_id == objective.objective_id
    assert run.status == RunStatus.RUNNING

    task = Task(
        run_id=run.run_id,
        objective_id=objective.objective_id,
        capability="cap",
        objective="sub",
    )
    assert task.run_id == run.run_id
    assert task.objective_id == objective.objective_id
    assert task.task_id == task.id


def test_agent_call_carries_full_ancestry() -> None:
    call = AgentCall(
        task_id="t1",
        run_id="r1",
        objective_id="o1",
        spawned_by="venture",
        capability="market_analysis",
        objective="analyse",
    )
    assert call.task_id == "t1"
    assert call.run_id == "r1"
    assert call.objective_id == "o1"
    assert call.status == TaskStatus.PENDING


async def test_run_carries_full_hierarchy(harness: Harness) -> None:
    """Every Task in a Run knows its run_id and objective_id."""
    run = await harness.run_pipeline("Analyse the options market for SPY")
    assert run.objective_id
    assert run.run_id
    for task in run.tasks:
        assert task.run_id == run.run_id
        assert task.objective_id == run.objective_id


async def test_harness_messages_carry_ancestry(harness: Harness) -> None:
    """TASK messages flowing through the bus carry objective_id, run_id, task_id."""
    captured = []
    original_enqueue = harness.bus.enqueue

    async def capturing_enqueue(destination, message):
        captured.append(message)
        return await original_enqueue(destination, message)

    harness.bus.enqueue = capturing_enqueue  # type: ignore[method-assign]

    await harness.run_pipeline("Test ancestry propagation")
    task_messages = [m for m in captured if m.message_type.value == "TASK"]
    assert task_messages
    for msg in task_messages:
        assert "objective_id" in msg.metadata
        assert "run_id" in msg.metadata
        assert "task_id" in msg.metadata
