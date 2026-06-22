"""Harness FastAPI entry point.

Exposes the harness over HTTP: intake, pipeline tracking, the brain registry,
the Judgment Ledger, doctrine, and the real-time Observer event stream. The
harness lifecycle is tied to the app lifespan so a single process boots the
whole nervous system.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from intake.api import create_intake_router
from harness.api.errors import CorrelationIdMiddleware, register_error_handlers
from harness.config import get_settings
from harness.core.errors import HarnessError
from harness.core.harness import Harness
from harness.schemas.chat import ChatRequest
from harness.schemas.judgment import OutcomeRecord

_harness: Harness | None = None


def get_harness() -> Harness:
    """Return the live harness instance or raise if not initialized."""
    if _harness is None:
        raise HarnessError(
            "Harness is not initialized",
            code="HARNESS_NOT_READY",
            source="api",
            status_code=503,
        )
    return _harness


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the harness on app startup and shut it down on exit."""
    global _harness
    _harness = Harness()
    await _harness.startup()
    try:
        yield
    finally:
        await _harness.shutdown()
        _harness = None


def create_app() -> FastAPI:
    """Construct and configure the harness FastAPI application."""
    settings = get_settings()
    allowed_origins = ["http://localhost:3000", "http://localhost:8000"]
    if settings.frontend_url:
        allowed_origins.append(settings.frontend_url.rstrip("/"))

    app = FastAPI(
        title="Blvckshell Harness",
        description="The nervous system of an autonomous organization.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins if settings.frontend_url else ["*"],
        allow_credentials=bool(settings.frontend_url),
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(CorrelationIdMiddleware)
    register_error_handlers(app)
    app.include_router(create_intake_router(get_harness))

    @app.post("/chat", tags=["chat"])
    async def chat(chat_request: ChatRequest) -> dict[str, Any]:
        """Send a message to Blvckbot and receive a coordinated response."""
        attachments = (
            [a.model_dump(mode="json") for a in chat_request.attachments]
            if chat_request.attachments
            else None
        )
        return await get_harness().run_chat(
            chat_request.message,
            session_id=chat_request.session_id,
            attachments=attachments,
        )

    @app.get("/chat/history/{session_id}", tags=["chat"])
    async def chat_history(session_id: str, limit: int = Query(default=50, ge=1, le=500)):
        """Return conversation history for a session."""
        entries = await get_harness().memory.conversations.get_history(session_id, limit=limit)
        return [e.model_dump(mode="json") for e in entries]

    @app.get("/chat/sessions", tags=["chat"])
    async def chat_sessions(limit: int = Query(default=50, ge=1, le=200)):
        """List recent chat sessions."""
        sessions = await get_harness().memory.conversations.list_sessions(limit=limit)
        return [s.model_dump(mode="json") for s in sessions]

    @app.post("/judgments/{judgment_id}/outcome", tags=["memory"])
    async def record_judgment_outcome(judgment_id: str, outcome: OutcomeRecord):
        """Record the real-world outcome for a judgment entry."""
        entry = await get_harness().memory.record_outcome(judgment_id, outcome)
        if entry is None:
            raise HTTPException(
                status_code=404,
                detail=f"Judgment '{judgment_id}' was not found in the ledger",
            )
        return entry.model_dump(mode="json")

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, Any]:
        """Liveness probe with environment summary."""
        harness = get_harness()
        return {
            "status": "ok",
            "environment": harness.settings.environment,
            "in_memory": harness.settings.use_in_memory_bus,
            "anthropic": harness.settings.anthropic_enabled,
        }

    @app.get("/brains", tags=["registry"])
    async def list_brains() -> list[dict[str, Any]]:
        """Return all registered brains and their live state (for status orbs)."""
        brains = await get_harness().registry.list_all()
        return [b.model_dump(mode="json") for b in brains]

    @app.get("/pipelines", tags=["pipelines"])
    async def list_pipelines() -> list[dict[str, Any]]:
        """Return recent pipelines for the live pipeline view."""
        return get_harness().list_pipelines()

    @app.get("/pipelines/{pipeline_id}", tags=["pipelines"])
    async def get_pipeline(pipeline_id: str) -> dict[str, Any]:
        """Return the current state of a single pipeline run."""
        run = await get_harness().get_pipeline(pipeline_id)
        if run is None:
            raise HTTPException(
                status_code=404,
                detail=f"Pipeline '{pipeline_id}' was not found",
            )
        return run

    @app.get("/ledger", tags=["memory"])
    async def list_ledger(
        brain_id: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=500),
    ) -> list[dict[str, Any]]:
        """Return recent Judgment Ledger entries, optionally filtered by brain."""
        entries = await get_harness().memory.ledger.list_recent(brain_id=brain_id, limit=limit)
        return [e.model_dump(mode="json") for e in entries]

    @app.get("/doctrine", tags=["memory"])
    async def list_doctrine(
        limit: int = Query(default=100, ge=1, le=500),
    ) -> list[dict[str, Any]]:
        """Return active (non-retired) doctrine — the system's accumulated wisdom."""
        entries = await get_harness().memory.doctrine.list_active(limit=limit)
        return [e.model_dump(mode="json") for e in entries]

    @app.get("/memory/notes", tags=["memory"])
    async def list_notes(
        operator_id: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=500),
    ) -> list[dict[str, Any]]:
        """Return recent durable memory notes, newest first."""
        entries = await get_harness().memory.notes.list_recent(operator_id=operator_id, limit=limit)
        return [e.model_dump(mode="json") for e in entries]

    @app.get("/memory/opinions", tags=["memory"])
    async def list_opinions(
        operator_id: str | None = Query(default=None),
        include_retired: bool = Query(default=False),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> list[dict[str, Any]]:
        """Return standing opinions, newest first (active only by default)."""
        if include_retired:
            entries = await get_harness().memory.opinions.list_all(
                operator_id=operator_id, limit=limit
            )
        else:
            entries = await get_harness().memory.opinions.list_active(
                operator_id=operator_id, limit=limit
            )
        return [e.model_dump(mode="json") for e in entries]

    @app.get("/memory/search", tags=["memory"])
    async def search_memory(
        q: str = Query(min_length=1),
        operator_id: str | None = Query(default=None),
        limit: int = Query(default=5, ge=1, le=50),
    ) -> dict[str, Any]:
        """Semantically search notes and opinions for the given query."""
        memory = get_harness().memory
        notes = await memory.recall_notes(q, operator_id=operator_id, limit=limit)
        opinions = await memory.recall_opinions(q, operator_id=operator_id, limit=limit)
        return {
            "notes": [n.model_dump(mode="json") for n in notes],
            "opinions": [o.model_dump(mode="json") for o in opinions],
        }

    @app.get("/observer/events", tags=["observer"])
    async def observer_events(
        context_id: str | None = Query(default=None),
        limit: int = Query(default=200, ge=1, le=1000),
    ) -> list[dict[str, Any]]:
        """Return recent audit events for the Observer view."""
        events = await get_harness().observer.list_recent(context_id=context_id, limit=limit)
        return [e.model_dump(mode="json") for e in events]

    @app.get("/observer/stream", tags=["observer"])
    async def observer_stream() -> StreamingResponse:
        """Stream audit events live as Server-Sent Events."""

        async def event_source():
            observer = get_harness().observer
            queue: asyncio.Queue[tuple[str, object | None]] = asyncio.Queue()

            async def pump_events() -> None:
                try:
                    async for event in observer.stream():
                        await queue.put(("event", event))
                except asyncio.CancelledError:
                    raise
                finally:
                    await queue.put(("done", None))

            async def send_heartbeats() -> None:
                try:
                    while True:
                        await asyncio.sleep(15)
                        await queue.put(("heartbeat", None))
                except asyncio.CancelledError:
                    return

            pump = asyncio.create_task(pump_events())
            heartbeat = asyncio.create_task(send_heartbeats())
            try:
                while True:
                    kind, payload = await queue.get()
                    if kind == "done":
                        break
                    if kind == "heartbeat":
                        yield ": heartbeat\n\n"
                        continue
                    event = payload
                    yield f"data: {json.dumps(event.model_dump(mode='json'))}\n\n"  # type: ignore[union-attr]
            finally:
                pump.cancel()
                heartbeat.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await pump
                    await heartbeat

        return StreamingResponse(event_source(), media_type="text/event-stream")

    return app


app = create_app()


def run() -> None:
    """Run the harness API with uvicorn (the ``blvckshell-harness`` script)."""
    import uvicorn

    settings = Harness().settings
    uvicorn.run(
        "harness.api.main:app",
        host="0.0.0.0",
        port=8000,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run()
