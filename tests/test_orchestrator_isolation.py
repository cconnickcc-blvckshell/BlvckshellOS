"""Tests proving the Orchestrator is harness-internal, not a brain (Change 3)."""

from __future__ import annotations

from brains._base.brain import BaseBrain
from harness.core.harness import Harness
from harness.core.orchestrator import Orchestrator


def test_orchestrator_is_not_a_brain(harness: Harness) -> None:
    """The Orchestrator must not extend BaseBrain."""
    assert isinstance(harness.orchestrator, Orchestrator)
    assert not isinstance(harness.orchestrator, BaseBrain)
    assert not issubclass(Orchestrator, BaseBrain)


def test_orchestrator_is_not_registered_as_worker(harness: Harness) -> None:
    """The orchestrator must not appear among the worker brains."""
    assert not any(b.brain_id in ("ckos", "orchestrator") for b in harness.workers)


async def test_orchestrator_not_in_registry() -> None:
    """The orchestrator never registers with the brain registry."""
    from harness.config import Settings

    harness = Harness(
        settings=Settings(use_in_memory_bus=True, use_fake_llm=True, log_level="WARNING")
    )
    await harness.startup()
    try:
        all_brains = await harness.registry.list_all()
        brain_ids = {b.brain_id for b in all_brains}
        assert "ckos" not in brain_ids
        assert "orchestrator" not in brain_ids
    finally:
        await harness.shutdown()


def test_ckos_module_is_deleted() -> None:
    """The brains/ckos package must no longer be importable."""
    import importlib

    try:
        importlib.import_module("brains.ckos.brain")
    except ModuleNotFoundError:
        return
    raise AssertionError("brains.ckos.brain should have been deleted")
