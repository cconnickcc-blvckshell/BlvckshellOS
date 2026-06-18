"""Four-outcome decision vocabulary (V2 default)."""

from __future__ import annotations

from enum import Enum


class JudgmentOutcome(str, Enum):
    """Canonical judgment outcomes — not task success/failure."""

    PROCEED = "PROCEED"
    STAGED_PROCEED = "STAGED_PROCEED"
    REQUEST_MORE_EVIDENCE = "REQUEST_MORE_EVIDENCE"
    HOLD = "HOLD"
