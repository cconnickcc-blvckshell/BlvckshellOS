"""Tests for dynamic brain loading from configuration (Change 2)."""

from __future__ import annotations

from harness.config import Settings
from harness.core.brain_loader import instantiate_brains, load_brain_classes
from harness.core.harness import Harness


def _settings(modules: str) -> Settings:
    return Settings(
        worker_brain_modules=modules,
        use_in_memory_bus=True,
        use_fake_llm=True,
        log_level="WARNING",
    )


def test_load_brain_classes_parses_entries() -> None:
    classes, failures = load_brain_classes(
        "brains.examples.venture:VentureBrain,brains.examples.commander:CommanderBrain"
    )
    assert [c.__name__ for c in classes] == ["VentureBrain", "CommanderBrain"]
    assert failures == []


def test_load_brain_classes_empty_string() -> None:
    assert load_brain_classes("") == ([], [])
    assert load_brain_classes("   ") == ([], [])


def test_load_brain_classes_skips_bad_entries() -> None:
    classes, failures = load_brain_classes(
        "does.not.exist:FakeBrain,brains.examples.venture:VentureBrain"
    )
    assert [c.__name__ for c in classes] == ["VentureBrain"]
    assert len(failures) == 1


def test_load_brain_classes_rejects_non_brain() -> None:
    # A real importable class that is not a BaseBrain must be skipped.
    classes, failures = load_brain_classes("harness.config:Settings")
    assert classes == []
    assert failures == []


async def test_dynamic_brain_loading_from_config() -> None:
    """Harness loads brains from config string, not hardcoded imports."""
    harness = Harness(settings=_settings("brains.examples.venture:VentureBrain"))
    await harness.startup()
    try:
        assert len(harness.workers) == 1
        assert harness.workers[0].brain_id == "venture"
    finally:
        await harness.shutdown()


async def test_unknown_brain_module_is_skipped_not_raised() -> None:
    """A bad module path logs an error but does not crash the harness."""
    harness = Harness(
        settings=_settings("does.not.exist:FakeBrain,brains.examples.venture:VentureBrain")
    )
    await harness.startup()
    try:
        assert len(harness.workers) == 1  # bad entry skipped, good one loaded
    finally:
        await harness.shutdown()


def test_instantiate_brains_uses_shared_runtime() -> None:
    harness = Harness(settings=_settings("brains.examples.venture:VentureBrain"))
    classes, _ = load_brain_classes("brains.examples.venture:VentureBrain")
    brains = instantiate_brains(classes, harness.runtime)
    assert brains[0].runtime is harness.runtime
