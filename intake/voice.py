"""Voice intake — transcribe audio into text, then hand off to text intake.

Transcription is pluggable behind :class:`Transcriber`. A deterministic stub is
used when no transcription backend is configured, so the path is always present
and testable; wire in Whisper (local or API) for production.
"""

from __future__ import annotations

import abc

from harness.core.logging import get_logger

from intake.text import normalize_text

logger = get_logger(__name__)


class Transcriber(abc.ABC):
    """Abstract speech-to-text transcriber."""

    @abc.abstractmethod
    async def transcribe(self, audio: bytes) -> str:
        """Transcribe raw audio bytes to text.

        Args:
            audio: Raw audio bytes (e.g. a WAV/MP3 payload).

        Returns:
            The transcribed text.
        """


class StubTranscriber(Transcriber):
    """Offline transcriber placeholder used when no backend is configured."""

    async def transcribe(self, audio: bytes) -> str:
        """Return a deterministic placeholder describing the audio payload."""
        return f"[voice capture: {len(audio)} bytes — configure a Transcriber to decode]"


_transcriber: Transcriber = StubTranscriber()


def set_transcriber(transcriber: Transcriber) -> None:
    """Install the process-wide transcriber implementation.

    Args:
        transcriber: The transcriber to use for voice intake.
    """
    global _transcriber
    _transcriber = transcriber


async def transcribe_to_objective(audio: bytes) -> str:
    """Transcribe audio and normalize it into an objective string.

    Args:
        audio: Raw audio bytes.

    Returns:
        A normalized objective ready for CKOS.
    """
    text = await _transcriber.transcribe(audio)
    return normalize_text(text)
