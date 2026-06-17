"""The test that proves the harness works end to end with the new hierarchy.

Input: an operator statement. Expected: the orchestrator decomposes and routes
it, every brain executes and returns a result via the bus, judgments are logged,
the orchestrator aggregates into a coherent output, and the Observer captures the
full trace — all under a correct Objective -> Run -> Task ancestry.
"""

from __future__ import annotations

from harness.core.harness import Harness
from harness.schemas.audit import AuditEventType

STATEMENT = "I want to build a trading AI that outperforms the market"


async def test_full_pipeline_objective_to_run(harness: Harness) -> None:
    run = await harness.run_pipeline(STATEMENT)

    # Correct hierarchy.
    assert run.objective_id
    assert run.run_id
    assert run.objective_id != run.run_id

    # Tasks have full ancestry.
    assert all(t.run_id == run.run_id for t in run.tasks)
    assert all(t.objective_id == run.objective_id for t in run.tasks)

    # Brains from config were used (not hardcoded).
    routed = {t.assigned_brain for t in run.tasks}
    assert routed == {"venture", "commander", "capital"}

    # Every brain returned a result via the bus.
    assert len(run.results) == len(run.tasks)
    assert all(r.succeeded for r in run.results)

    # Output synthesized.
    assert run.output.strip()
    assert run.status.value in ("COMPLETED", "PARTIAL")


async def test_pipeline_logs_judgments_for_every_brain(harness: Harness) -> None:
    run = await harness.run_pipeline(STATEMENT)
    judgments = await harness.memory.ledger.list_for_context(run.run_id)
    authors = {j.brain_id for j in judgments}
    # The orchestrator logs the routing decision; each worker logs its own.
    assert "orchestrator" in authors
    assert {"venture", "commander", "capital"}.issubset(authors)


async def test_observer_captures_full_trace(harness: Harness) -> None:
    run = await harness.run_pipeline(STATEMENT)
    events = await harness.observer.list_recent(context_id=run.run_id, limit=500)
    types = {e.event_type for e in events}
    assert AuditEventType.PIPELINE_STARTED in types
    assert AuditEventType.PIPELINE_COMPLETED in types
    assert AuditEventType.TASK_STARTED in types
    assert AuditEventType.TASK_COMPLETED in types
    assert AuditEventType.LLM_CALL in types
    assert AuditEventType.JUDGMENT_CREATED in types


async def test_pipeline_state_is_queryable(harness: Harness) -> None:
    run = await harness.run_pipeline(STATEMENT)
    state = await harness.get_pipeline(run.objective_id)
    assert state is not None
    assert state["status"] == "COMPLETED"
    assert state["output"]
    assert len(state["plan"]) == 3


async def test_brain_failure_does_not_crash_harness(harness: Harness) -> None:
    # Break one brain mid-flight; the pipeline must degrade, not crash.
    async def boom(_message):
        raise RuntimeError("simulated brain failure")

    venture = next(b for b in harness.workers if b.brain_id == "venture")
    venture.handle_task = boom  # type: ignore[method-assign]

    run = await harness.run_pipeline(STATEMENT)
    statuses = {r.brain_id: r.status.value for r in run.results}
    assert statuses["venture"] == "FAILURE"
    # The other brains still succeeded and the orchestrator still synthesized.
    assert run.output.strip()
