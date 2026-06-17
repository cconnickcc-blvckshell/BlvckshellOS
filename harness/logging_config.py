"""Structured logging setup for the harness.

We use ``structlog`` so every log line is structured JSON-friendly key/value
data, which is essential for the Observer and for eventually training on real
pipeline data.
"""

from __future__ import annotations

import logging
import sys

import structlog

_CONFIGURED = False


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog and the stdlib logging bridge exactly once.

    Args:
        level: The root log level name (e.g. ``"INFO"``, ``"DEBUG"``).
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _CONFIGURED = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger for the given component name.

    Args:
        name: The component name, attached as ``component`` on every log line.

    Returns:
        A bound logger ready for structured logging.
    """
    return structlog.get_logger(component=name)
