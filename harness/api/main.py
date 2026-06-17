"""Harness FastAPI entry point — wires every layer into one running service.

On startup it builds the runtime, starts the default brain federation, and the
intake service. It exposes read APIs over the registry, Judgment Ledger,
doctrine store and observer, plus a live observer event stream (SSE).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from intake.api import router as intake_router
from intake.service import IntakeService

from harness.bootstrap import default_brains, start_brains, stop_brains
from harness.config import settings
from harness.core.logging import configure_logging, get_logger
from harness.core.runtime import create_runtime
from harness.schemas.event import ObserverEvent

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Start and stop the full harness alongside the HTTP server."""
    configure_logging()
    runtime = create_runtime()
    await runtime.start()
    brains = default_brains(runtime) if settings.inprocess_brains else []
    await start_brains(brains)
    intake = IntakeService(runtime)
    await intake.start()

    app.state.runtime = runtime
    app.state.brains = brains
    app.state.intake = intake
    logger.info("Harness API online with %d brains", len(brains))
    try:
        yield
    finally:
        await intake.stop()
        await stop_brains(brains)
        await runtime.stop()
        logger.info("Harness API shut down")


def create_app() -> FastAPI:
    """Construct the harness FastAPI application.

    Returns:
        A configured :class:`fastapi.FastAPI` instance.
    """
    app = FastAPI(
        title="Blvckshell Agent Harness",
        version="0.1.0",
        description="The nervous system of an autonomous organization.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(intake_router)
    _register_core_routes(app)
    return app


def _register_core_routes(app: FastAPI) -> None:
    """Register registry/ledger/doctrine/observer/pipeline routes."""

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, Any]:
        """Liveness probe with backend selection info."""
        return {
            "status": "ok",
            "environment": settings.environment,
            "inference_provider": settings.inference_provider,
            "bus": "redis" if settings.use_redis else "in-memory",
            "persistence": "supabase" if settings.use_supabase else "in-memory",
        }

    @app.get("/brains", tags=["registry"])
    async def list_brains(request: Request) -> dict[str, Any]:
        """Return every registered brain and its status."""
        brains = await request.app.state.runtime.registry.all()
        return {"brains": [b.model_dump(mode="json") for b in brains]}

    @app.get("/pipelines/{pipeline_id}", tags=["pipelines"])
    async def get_pipeline(request: Request, pipeline_id: str) -> dict[str, Any]:
        """Return a pipeline's working state, result and event trace."""
        runtime = request.app.state.runtime
        intake: IntakeService = request.app.state.intake
        working = await runtime.memory.context.get_all(pipeline_id)
        result = intake.result_for(pipeline_id)
        events = runtime.observer.recent(limit=200, context_id=pipeline_id)
        return {
            "pipeline_id": pipeline_id,
            "working": working,
            "result": result.model_dump(mode="json") if result else None,
            "events": [e.model_dump(mode="json") for e in events],
        }

    @app.get("/judgments", tags=["memory"])
    async def list_judgments(request: Request, brain_id: str | None = None) -> dict[str, Any]:
        """Return Judgment Ledger entries, optionally filtered by brain."""
        ledger = request.app.state.runtime.memory.ledger
        entries = await (ledger.for_brain(brain_id) if brain_id else ledger.all())
        return {"judgments": [e.model_dump(mode="json") for e in entries]}

    @app.get("/doctrine", tags=["memory"])
    async def list_doctrine(request: Request) -> dict[str, Any]:
        """Return active (non-superseded) doctrine."""
        doctrine = await request.app.state.runtime.memory.doctrine.active()
        return {"doctrine": doctrine}

    @app.get("/observer", tags=["observer"])
    async def list_events(request: Request, limit: int = 100) -> dict[str, Any]:
        """Return recent observer events from the in-memory ring."""
        events = request.app.state.runtime.observer.recent(limit=limit)
        return {"events": [e.model_dump(mode="json") for e in events]}

    @app.get("/observer/stream", tags=["observer"])
    async def stream_events(request: Request) -> StreamingResponse:
        """Stream observer events live as server-sent events."""
        observer = request.app.state.runtime.observer
        queue: asyncio.Queue[ObserverEvent] = asyncio.Queue()

        async def _subscriber(event: ObserverEvent) -> None:
            await queue.put(event)

        observer.subscribe(_subscriber)

        async def _generate() -> AsyncIterator[str]:
            try:
                while True:
                    event = await queue.get()
                    yield f"data: {json.dumps(event.model_dump(mode='json'))}\n\n"
            finally:
                observer.unsubscribe(_subscriber)

        return StreamingResponse(_generate(), media_type="text/event-stream")


app = create_app()


def run() -> None:
    """Run the harness API with uvicorn (console-script entry point)."""
    import uvicorn

    uvicorn.run(
        "harness.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.environment == "local",
    )


if __name__ == "__main__":
    run()
