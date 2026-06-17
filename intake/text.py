"""Text intake — normalize raw operator text into a clean objective."""

from __future__ import annotations

import re

_WHITESPACE = re.compile(r"\s+")


def normalize_text(raw: str) -> str:
    """Normalize raw captured text into a single clean objective string.

    Collapses whitespace and trims. Intentionally light-touch: CKOS is
    responsible for interpreting intent, not this layer.

    Args:
        raw: The raw captured text.

    Returns:
        A normalized objective string.

    Raises:
        ValueError: If the input is empty after normalization.
    """
    cleaned = _WHITESPACE.sub(" ", raw or "").strip()
    if not cleaned:
        raise ValueError("intake text is empty")
    return cleaned
