"""Intake API — the operator's entry point for injecting ideas.

The operator must be able to drop an idea in under 10 seconds from any state.
This module defines the intake request/response schemas and an ``APIRouter``
exposing text, quick-capture, and voice intake plus pipeline tracking.
"""

from __future__ import annotations

import base64
import uuid
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from intake.text import normalize_text
from intake.voice import PassthroughTranscriber, Transcriber, transcribe_to_idea


class IntakeRequest(BaseModel):
    """A text/quick-capture intake submission.

    Attributes:
        text: The raw idea text from the operator.
        wait: If true, block until the pipeline completes and return the result.
    """

    text: str = Field(min_length=1)
    wait: bool = False


class VoiceIntakeRequest(BaseModel):
    """A voice intake submission carrying base64-encoded audio.

    Attributes:
        audio_base64: Base64-encoded audio bytes to transcribe.
        wait: If true, block until the pipeline completes.
    """

    audio_base64: str
    wait: bool = False


class IntakeResponse(BaseModel):
    """The immediate acknowledgment returned for an intake submission.

    Attributes:
        pipeline_id: The id to track the pipeline run.
        status: ``running`` for async, or a terminal status when ``wait``.
        message: A short operator-facing acknowledgment.
        idea: The normalized idea that was accepted.
        result: The full pipeline run, present only when ``wait`` is true.
    """

    pipeline_id: str
    status: str
    message: str
    idea: str
    result: dict[str, Any] | None = None


def create_intake_router(
    get_harness: Callable[[], Any],
    *,
    transcriber: Transcriber | None = None,
) -> APIRouter:
    """Build the intake ``APIRouter`` bound to a harness accessor.

    Args:
        get_harness: A callable returning the live :class:`~harness.core.harness.Harness`.
        transcriber: Optional transcriber for voice intake (defaults to passthrough).

    Returns:
        A configured :class:`fastapi.APIRouter`.
    """
    router = APIRouter(prefix="/intake", tags=["intake"])
    _transcriber = transcriber or PassthroughTranscriber()

    async def _launch(idea: str, wait: bool) -> IntakeResponse:
        """Start a pipeline for an idea, awaiting it only when requested."""
        harness = get_harness()
        context_id = str(uuid.uuid4())
        harness.track_pipeline(context_id, idea)

        if wait:
            run = await harness.run_pipeline(idea, context_id=context_id)
            return IntakeResponse(
                pipeline_id=context_id,
                status=run.status,
                message="Pipeline complete.",
                idea=idea,
                result=run.to_dict(),
            )

        harness.spawn_pipeline(idea, context_id)
        return IntakeResponse(
            pipeline_id=context_id,
            status="running",
            message="Got it, running.",
            idea=idea,
        )

    @router.post("", response_model=IntakeResponse)
    async def submit(request: IntakeRequest) -> IntakeResponse:
        """Accept a text idea and launch a pipeline."""
        try:
            idea = normalize_text(request.text)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return await _launch(idea, request.wait)

    @router.post("/voice", response_model=IntakeResponse)
    async def submit_voice(request: VoiceIntakeRequest) -> IntakeResponse:
        """Transcribe a voice submission and launch a pipeline."""
        try:
            audio = base64.b64decode(request.audio_base64)
            idea = await transcribe_to_idea(_transcriber, audio)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return await _launch(idea, request.wait)

    return router
