"""The test that proves it works — a full pipeline, end to end.

Input: "I want to build a trading AI that outperforms the market".

CKOS receives, decomposes, routes to Venture / Commander / Capital, each brain
executes and logs a judgment, CKOS aggregates, and the observer captures the
full trace. If this passes, the harness is real.
"""

from __future__ import annotations

from harness.core.runtime import HarnessRuntime
from harness.schemas.event import EventType
from harness.schemas.result import ResultStatus
from intake.service import IntakeService

OBJECTIVE = "I want to build a trading AI that outperforms the market"


async def test_full_pipeline_idea_to_result(
    running_harness: tuple[HarnessRuntime, IntakeService],
) -> None:
    runtime, intake = running_harness

    pipeline_id = await intake.submit(OBJECTIVE)
    assert pipeline_id

    result = await intake.await_result(pipeline_id, timeout=30.0)
    assert result is not None, "pipeline did not complete"
    assert result.status == ResultStatus.SUCCESS
    assert result.brain_id == "ckos"

    # CKOS decomposed into one task per worker brain (venture, commander, capital).
    tasks = result.output["tasks"]
    assert {row["brain_id"] for row in tasks} == {"venture", "commander", "capital"}
    assert result.output["failed"] == 0

    # Every brain logged a judgment for this run.
    judgments = await runtime.memory.ledger.for_context(pipeline_id)
    judging_brains = {j.brain_id for j in judgments}
    assert "ckos" in judging_brains
    assert {"venture", "commander", "capital"} <= judging_brains

    # The pipeline run is persisted to episodic memory.
    episode = await runtime.memory.episodic.get(pipeline_id)
    assert episode is not None
    assert episode["objective"] == OBJECTIVE

    # The observer captured the full trace.
    events = runtime.observer.recent(limit=500, context_id=pipeline_id)
    event_types = {e.event_type for e in events}
    assert EventType.PIPELINE_STARTED in event_types
    assert EventType.PIPELINE_COMPLETED in event_types
    assert EventType.TASK_STARTED in event_types
    assert EventType.TASK_COMPLETED in event_types
    assert EventType.LLM_CALL in event_types
    assert EventType.JUDGMENT_CREATED in event_types


async def test_pipeline_blocks_when_no_workers() -> None:
    # A CKOS with no worker brains must escalate, not crash.
    from brains.ckos import CKOSBrain
    from harness.core.runtime import create_runtime

    runtime = create_runtime()
    await runtime.start()
    ckos = CKOSBrain(runtime)
    await ckos.start()
    intake = IntakeService(runtime)
    await intake.start()
    try:
        pipeline_id = await intake.submit("do something impossible")
        result = await intake.await_result(pipeline_id, timeout=15.0)
        assert result is not None
        assert result.status == ResultStatus.BLOCKED
        assert result.error == "no_capable_brains"
    finally:
        await intake.stop()
        await ckos.stop()
        await runtime.stop()
