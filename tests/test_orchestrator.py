"""Tests for the harness Orchestrator planning and synthesis."""

from __future__ import annotations

from harness.config import Settings
from harness.core.llm import FakeLLMClient, LLMResponse
from harness.core.memory import build_shared_memory
from harness.core.observer import InMemoryAuditStore, Observer
from harness.core.orchestrator import Orchestrator, _extract_json
from harness.core.registry import InMemoryBrainRegistry
from harness.schemas.brain_info import BrainInfo
from harness.schemas.objective import Objective, Run
from harness.schemas.result import Result, ResultStatus


def _settings() -> Settings:
    return Settings(use_in_memory_bus=True, use_fake_llm=True)


async def _orchestrator(llm, *, with_brains: bool = True) -> Orchestrator:
    settings = _settings()
    observer = Observer(InMemoryAuditStore())
    registry = InMemoryBrainRegistry()
    memory = build_shared_memory(settings, observer)
    await memory.connect()
    if with_brains:
        await registry.register(
            BrainInfo(
                brain_id="venture", name="Venture", description="Validate", capabilities=["v"]
            )
        )
        await registry.register(
            BrainInfo(brain_id="commander", name="Cmd", description="Plan", capabilities=["e"])
        )
    return Orchestrator(llm=llm, registry=registry, memory=memory, observer=observer)


def test_extract_json_handles_fences() -> None:
    assert _extract_json('```json\n{"tasks": []}\n```') == {"tasks": []}
    assert _extract_json('prefix {"a": 1} suffix') == {"a": 1}
    assert _extract_json("no json here") is None


async def test_heuristic_plan_routes_to_all_registered_brains() -> None:
    orch = await _orchestrator(FakeLLMClient())  # default fake returns prose, not JSON
    objective = Objective(statement="build a trading AI")
    run = Run(objective_id=objective.objective_id)
    tasks = await orch.plan(objective, run)
    assert {t.assigned_brain for t in tasks} == {"venture", "commander"}
    # Every task carries full ancestry.
    assert all(t.run_id == run.run_id for t in tasks)
    assert all(t.objective_id == objective.objective_id for t in tasks)


async def test_llm_plan_respects_registry_capabilities() -> None:
    plan_json = (
        '{"tasks": [{"capability": "v", "objective": "validate", "depends_on": []},'
        '{"capability": "ghost", "objective": "ignored", "depends_on": []}]}'
    )
    orch = await _orchestrator(FakeLLMClient(scripted=[LLMResponse(text=plan_json)]))
    objective = Objective(statement="idea")
    run = Run(objective_id=objective.objective_id)
    tasks = await orch.plan(objective, run)
    assert len(tasks) == 1
    assert tasks[0].assigned_brain == "venture"


async def test_plan_logs_routing_judgment_under_run_id() -> None:
    orch = await _orchestrator(FakeLLMClient())
    objective = Objective(statement="idea")
    run = Run(objective_id=objective.objective_id)
    await orch.plan(objective, run)
    judgments = await orch._memory.ledger.list_for_context(run.run_id)
    assert any(j.brain_id == "orchestrator" for j in judgments)


async def test_synthesize_offline_fallback() -> None:
    orch = await _orchestrator(FakeLLMClient())
    objective = Objective(statement="idea")
    run = Run(objective_id=objective.objective_id)
    results = [
        Result(task_id="t1", brain_id="venture", status=ResultStatus.SUCCESS, summary="GO"),
        Result(
            task_id="t2",
            brain_id="commander",
            status=ResultStatus.FAILURE,
            summary="",
            error="boom",
        ),
    ]
    synthesis = await orch.synthesize(objective, run, results)
    assert "venture" in synthesis
    assert "BLOCKED" in synthesis


async def test_plan_with_no_brains_returns_empty() -> None:
    orch = await _orchestrator(FakeLLMClient(), with_brains=False)
    objective = Objective(statement="idea")
    run = Run(objective_id=objective.objective_id)
    assert await orch.plan(objective, run) == []
