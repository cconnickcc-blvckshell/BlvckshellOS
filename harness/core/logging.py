"""Structured-ish logging helpers built on the stdlib (zero extra deps)."""

from __future__ import annotations

import logging
import sys

from harness.config import settings

_CONFIGURED = False


def configure_logging() -> None:
    """Configure root logging once, honoring the configured log level."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger for ``name``.

    Args:
        name: Logger name, typically ``__name__`` of the calling module.

    Returns:
        A ready-to-use :class:`logging.Logger`.
    """
    configure_logging()
    return logging.getLogger(name)
