"""Voice intake — transcribe audio to text, then hand off to text intake.

Transcription is pluggable behind :class:`Transcriber` so the harness does not
hard-depend on any specific speech engine. A Whisper-backed transcriber is the
intended production default; a passthrough transcriber keeps the path testable
offline.
"""

from __future__ import annotations

import abc

from intake.text import normalize_text


class Transcriber(abc.ABC):
    """Abstract speech-to-text transcriber."""

    @abc.abstractmethod
    async def transcribe(self, audio: bytes) -> str:
        """Transcribe raw audio bytes into text."""


class PassthroughTranscriber(Transcriber):
    """Decodes UTF-8 'audio' as text — for tests and offline development."""

    async def transcribe(self, audio: bytes) -> str:
        """Return the audio bytes decoded as UTF-8 text."""
        return audio.decode("utf-8", errors="ignore")


class WhisperTranscriber(Transcriber):
    """Whisper-backed transcriber (loaded lazily to keep imports cheap)."""

    def __init__(self, model_name: str = "base") -> None:
        """Create the transcriber.

        Args:
            model_name: The Whisper model size to load on first use.
        """
        self._model_name = model_name
        self._model = None

    async def transcribe(self, audio: bytes) -> str:
        """Transcribe audio bytes using a local Whisper model.

        Args:
            audio: Raw audio file bytes (e.g. WAV/MP3 contents).

        Returns:
            The transcribed text.
        """
        import tempfile

        import whisper  # type: ignore[import-not-found]

        if self._model is None:
            self._model = whisper.load_model(self._model_name)
        with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
            tmp.write(audio)
            tmp.flush()
            result = self._model.transcribe(tmp.name)
        return str(result.get("text", ""))


async def transcribe_to_idea(transcriber: Transcriber, audio: bytes) -> str:
    """Transcribe audio and normalize it into an idea string.

    Args:
        transcriber: The transcriber to use.
        audio: Raw audio bytes.

    Returns:
        A cleaned idea string ready for CKOS.
    """
    text = await transcriber.transcribe(audio)
    return normalize_text(text)
