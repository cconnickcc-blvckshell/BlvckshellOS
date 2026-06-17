"""Tests for CKOS planning and synthesis."""

from __future__ import annotations

from brains._base.brain import BrainRuntime
from brains.ckos.brain import CKOSBrain, _extract_json
from harness.config import Settings
from harness.core.llm import FakeLLMClient, LLMResponse
from harness.core.memory import build_shared_memory
from harness.core.message_bus import InMemoryMessageBus
from harness.core.observer import InMemoryAuditStore, Observer
from harness.core.registry import InMemoryBrainRegistry
from harness.schemas.brain_info import BrainInfo
from harness.schemas.result import Result, ResultStatus


def _settings() -> Settings:
    return Settings(use_in_memory_bus=True, use_fake_llm=True)


async def _runtime(llm) -> BrainRuntime:
    settings = _settings()
    observer = Observer(InMemoryAuditStore())
    registry = InMemoryBrainRegistry()
    memory = build_shared_memory(settings, observer)
    await memory.connect()
    bus = InMemoryMessageBus()
    await bus.connect()
    await registry.register(
        BrainInfo(brain_id="venture", name="Venture", description="Validate", capabilities=["v"])
    )
    await registry.register(
        BrainInfo(brain_id="commander", name="Cmd", description="Plan", capabilities=["e"])
    )
    return BrainRuntime(
        bus=bus, registry=registry, memory=memory, observer=observer, llm=llm, settings=settings
    )


def test_extract_json_handles_fences() -> None:
    assert _extract_json('```json\n{"tasks": []}\n```') == {"tasks": []}
    assert _extract_json("prefix {\"a\": 1} suffix") == {"a": 1}
    assert _extract_json("no json here") is None


async def test_heuristic_plan_routes_to_all_registered_brains() -> None:
    runtime = await _runtime(FakeLLMClient())  # default fake returns prose, not JSON
    ckos = CKOSBrain(runtime)
    tasks = await ckos.plan("build a trading AI", "c1")
    routed = {t.assigned_brain for t in tasks}
    assert routed == {"venture", "commander"}


async def test_llm_plan_respects_registry_capabilities() -> None:
    plan_json = (
        '{"tasks": [{"capability": "v", "objective": "validate", "depends_on": []},'
        '{"capability": "ghost", "objective": "ignored", "depends_on": []}]}'
    )
    llm = FakeLLMClient(scripted=[LLMResponse(text=plan_json)])
    runtime = await _runtime(llm)
    ckos = CKOSBrain(runtime)
    tasks = await ckos.plan("idea", "c1")
    # The 'ghost' capability is not registered and must be dropped.
    assert len(tasks) == 1
    assert tasks[0].assigned_brain == "venture"


async def test_plan_logs_routing_judgment() -> None:
    runtime = await _runtime(FakeLLMClient())
    ckos = CKOSBrain(runtime)
    await ckos.plan("idea", "c1")
    judgments = await runtime.memory.ledger.list_for_context("c1")
    assert any(j.brain_id == "ckos" for j in judgments)


async def test_synthesize_offline_fallback() -> None:
    runtime = await _runtime(FakeLLMClient())
    ckos = CKOSBrain(runtime)
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
    synthesis = await ckos.synthesize("idea", results, "c1")
    assert "venture" in synthesis
    assert "BLOCKED" in synthesis


async def test_plan_with_no_workers_returns_empty() -> None:
    settings = _settings()
    observer = Observer(InMemoryAuditStore())
    memory = build_shared_memory(settings, observer)
    await memory.connect()
    bus = InMemoryMessageBus()
    await bus.connect()
    runtime = BrainRuntime(
        bus=bus,
        registry=InMemoryBrainRegistry(),
        memory=memory,
        observer=observer,
        llm=FakeLLMClient(),
        settings=settings,
    )
    ckos = CKOSBrain(runtime)
    assert await ckos.plan("idea", "c1") == []
