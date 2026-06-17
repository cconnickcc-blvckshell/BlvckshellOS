"""FastAPI router exposing the intake interface.

These endpoints are how the operator (or any program) injects ideas. They are
mounted by the harness API and operate on the shared :class:`IntakeService`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, File, Query, Request, UploadFile
from pydantic import BaseModel, Field

from intake.service import IntakeService
from intake.text import normalize_text
from intake.voice import transcribe_to_objective

router = APIRouter(prefix="/intake", tags=["intake"])


class IntakeRequest(BaseModel):
    """Body for a text/quick-capture intake."""

    text: str = Field(..., min_length=1, description="The raw captured idea.")
    priority: int = Field(default=4, ge=1, le=5)


class IntakeAck(BaseModel):
    """Immediate acknowledgment returned for every intake."""

    pipeline_id: str
    status: str = "running"
    message: str = "Got it, running"


def _service(request: Request) -> IntakeService:
    """Pull the shared intake service off the application state."""
    return request.app.state.intake


@router.post("", response_model=None)
async def intake_text(
    request: Request,
    body: Annotated[IntakeRequest, Body(...)],
    wait: Annotated[bool, Query(description="Block for the final result.")] = False,
) -> IntakeAck | dict[str, object]:
    """Capture a text idea and route it to CKOS.

    Args:
        request: The incoming request (provides app state).
        body: The intake payload.
        wait: When true, block until the pipeline completes and return its result.

    Returns:
        An :class:`IntakeAck`, or the full result dict when ``wait`` is true.
    """
    service = _service(request)
    objective = normalize_text(body.text)
    pipeline_id = await service.submit(objective, priority=body.priority)
    if not wait:
        return IntakeAck(pipeline_id=pipeline_id)
    result = await service.await_result(pipeline_id)
    return {
        "pipeline_id": pipeline_id,
        "status": "completed" if result else "timeout",
        "result": result.model_dump(mode="json") if result else None,
    }


@router.post("/voice", response_model=IntakeAck)
async def intake_voice(
    request: Request,
    audio: Annotated[UploadFile, File(description="Audio capture to transcribe.")],
) -> IntakeAck:
    """Capture a voice idea: transcribe, normalize, route to CKOS.

    Args:
        request: The incoming request (provides app state).
        audio: The uploaded audio file.

    Returns:
        An :class:`IntakeAck` with the pipeline id.
    """
    service = _service(request)
    payload = await audio.read()
    objective = await transcribe_to_objective(payload)
    pipeline_id = await service.submit(objective)
    return IntakeAck(pipeline_id=pipeline_id)
