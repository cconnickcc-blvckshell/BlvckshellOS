"""Harness FastAPI entry point.

Exposes the harness over HTTP: intake, pipeline tracking, the brain registry,
the Judgment Ledger, doctrine, and the real-time Observer event stream. The
harness lifecycle is tied to the app lifespan so a single process boots the
whole nervous system.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from intake.api import create_intake_router

from harness.core.harness import Harness

_harness: Harness | None = None


def get_harness() -> Harness:
    """Return the live harness instance or raise if not initialized."""
    if _harness is None:
        raise RuntimeError("harness not initialized")
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
    app = FastAPI(
        title="Blvckshell Harness",
        description="The nervous system of an autonomous organization.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(create_intake_router(get_harness))

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
            raise HTTPException(status_code=404, detail="pipeline not found")
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
            async for event in observer.stream():
                yield f"data: {json.dumps(event.model_dump(mode='json'))}\n\n"
                await asyncio.sleep(0)

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
