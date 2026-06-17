"""Text intake — normalize a raw operator message into a clean idea string."""

from __future__ import annotations


def normalize_text(raw: str) -> str:
    """Normalize raw operator text into a clean idea for CKOS.

    Collapses whitespace and trims. Kept intentionally small — CKOS does the
    semantic heavy lifting; intake only sanitizes.

    Args:
        raw: The raw operator input.

    Returns:
        A cleaned single-line idea string.

    Raises:
        ValueError: If the input is empty after normalization.
    """
    cleaned = " ".join(raw.split()).strip()
    if not cleaned:
        raise ValueError("intake text is empty")
    return cleaned
