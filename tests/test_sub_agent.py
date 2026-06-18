"""Tests for first-class sub-agent spawning (Change 4)."""

from __future__ import annotations

from harness.core.harness import Harness
from harness.schemas.audit import AuditEventType


async def test_brain_can_spawn_sub_agent(harness: Harness) -> None:
    """A brain can spawn a sub-agent and receive its result."""
    spawned_calls = []

    parent = next(b for b in harness.workers if b.brain_id == "commander")
    child = next(b for b in harness.workers if b.brain_id == "venture")
    original_handle = parent.handle_task

    async def handle_with_spawn(task_msg):
        call = await parent.spawn_agent(
            capability=child.capabilities[0],
            objective="Sub-task: provide a brief analysis",
            inputs={"context": "test"},
            parent_task_id=task_msg.payload.get("id", "unknown"),
            run_id=task_msg.metadata.get("run_id", task_msg.context_id),
            objective_id=task_msg.metadata.get("objective_id", "unknown"),
            timeout=30.0,
        )
        spawned_calls.append(call)
        return await original_handle(task_msg)

    parent.handle_task = handle_with_spawn  # type: ignore[method-assign]
    await harness.run_pipeline("Test sub-agent spawning")

    assert len(spawned_calls) >= 1
    assert spawned_calls[0].status.value == "COMPLETED"
    assert spawned_calls[0].result


async def test_sub_agent_events_are_recorded(harness: Harness) -> None:
    """Observer records AGENT_SPAWNED and AGENT_RETURNED on a successful spawn."""
    parent = next(b for b in harness.workers if b.brain_id == "commander")
    child = next(b for b in harness.workers if b.brain_id == "venture")
    original_handle = parent.handle_task

    async def handle_with_spawn(task_msg):
        await parent.spawn_agent(
            capability=child.capabilities[0],
            objective="Sub-task",
            parent_task_id=task_msg.payload.get("id", "unknown"),
            run_id=task_msg.metadata.get("run_id", task_msg.context_id),
            objective_id=task_msg.metadata.get("objective_id", "unknown"),
            timeout=30.0,
        )
        return await original_handle(task_msg)

    parent.handle_task = handle_with_spawn  # type: ignore[method-assign]
    run = await harness.run_pipeline("Test sub-agent events")

    events = await harness.observer.list_recent(context_id=run.run_id, limit=500)
    types = {e.event_type for e in events}
    assert AuditEventType.AGENT_SPAWNED in types
    assert AuditEventType.AGENT_RETURNED in types


async def test_spawn_agent_fails_gracefully_on_unknown_capability(harness: Harness) -> None:
    """spawn_agent returns FAILED status when no brain handles the capability."""
    brain = next(b for b in harness.workers if b.brain_id == "commander")
    call = await brain.spawn_agent(
        capability="capability_that_does_not_exist",
        objective="This should fail gracefully",
        parent_task_id="test-task-id",
        run_id="test-run-id",
        objective_id="test-objective-id",
        timeout=5.0,
    )
    assert call.status.value == "FAILED"
    assert call.error
    # Harness must still be running — a failed sub-agent is not a crash.
    assert harness._started
