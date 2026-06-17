"""Intake — capture an idea in under 10 seconds from any state.

Voice, text and programmatic API all funnel into one normalized objective that
is handed to CKOS. The operator gets an immediate ACK and a pipeline id.
"""

from intake.service import IntakeService
from intake.text import normalize_text

__all__ = ["IntakeService", "normalize_text"]
