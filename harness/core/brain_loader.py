"""Dynamic brain loading.

Brains are declared in configuration as ``module:ClassName`` paths, not hardcoded
in harness code. The harness imports each at startup. Adding a brain means
editing ``.env`` (``BLVCKSHELL_WORKER_BRAIN_MODULES``), never touching
``harness/core/harness.py``.

Loading is failure-isolated: an unknown or unimportable entry is logged and
skipped so the harness always starts, even if one brain fails to load.
"""

from __future__ import annotations

import importlib
from typing import Any

from brains._base.brain import BaseBrain, BrainRuntime

from harness.logging_config import get_logger

logger = get_logger("brain_loader")


def load_brain_classes(modules_str: str) -> tuple[list[type[BaseBrain]], list[dict[str, Any]]]:
    """Import brain classes from a comma-separated ``module:ClassName`` string.

    Unknown or unimportable entries are logged and skipped — they never raise, so
    the harness starts even if one brain fails to load.

    Args:
        modules_str: Comma-separated ``module:ClassName`` paths. Empty means no
            in-process brains.

    Returns:
        The successfully imported :class:`BaseBrain` subclasses, in order.
    """
    if not modules_str.strip():
        return [], []

    classes: list[type[BaseBrain]] = []
    failures: list[dict[str, Any]] = []
    for raw_entry in modules_str.split(","):
        entry = raw_entry.strip()
        if not entry:
            continue
        try:
            module_path, class_name = entry.rsplit(":", 1)
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
        except Exception as exc:
            error_message = str(exc).strip() or type(exc).__name__
            logger.error("brain_loader_failed", entry=entry, error=error_message)
            failures.append(
                {
                    "entry": entry,
                    "error": error_message,
                    "error_type": type(exc).__name__,
                }
            )
            continue

        if not (isinstance(cls, type) and issubclass(cls, BaseBrain)):
            logger.warning("brain_loader_not_a_brain", entry=entry)
            continue

        classes.append(cls)
        logger.info("brain_loader_loaded", brain=class_name)
    return classes, failures


def instantiate_brains(
    classes: list[type[BaseBrain]], runtime: BrainRuntime
) -> list[BaseBrain]:
    """Instantiate each brain class with the shared runtime.

    Args:
        classes: The brain classes to instantiate.
        runtime: The shared :class:`BrainRuntime` to inject into each.

    Returns:
        The instantiated brains.
    """
    return [cls(runtime) for cls in classes]
