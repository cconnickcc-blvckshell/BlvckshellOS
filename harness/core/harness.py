"""The Harness — the application context that wires every layer together.

This is the nervous system. It constructs the message bus, registry, shared
memory, observer, and LLM client; brings up CKOS and the specialist brains;
starts their serve loops; and exposes a single :meth:`run_pipeline` entry point
that intake calls.

Brains run in-process here by default (so a single ``docker compose up`` works),
but because everything communicates over the bus abstraction, brains can equally
run in their own containers against a shared Redis bus.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid

from brains._base.brain import BaseBrain, BrainRuntime
from brains.ckos.brain import CKOSBrain
from brains.examples.capital import CapitalBrain
from brains.examples.commander import CommanderBrain
from brains.examples.venture import VentureBrain

from harness.config import Settings, get_settings
from harness.core.llm import build_llm_client
from harness.core.memory import build_shared_memory
from harness.core.message_bus import build_message_bus
from harness.core.observer import (
    InMemoryAuditStore,
    Observer,
    SupabaseAuditStore,
)
from harness.core.registry import build_registry
from harness.core.router import PipelineRouter, PipelineRun
from harness.logging_config import configure_logging, get_logger

logger = get_logger("harness")

# Specialist brains shipped with the harness. New brains are added here (or, in
# production, run as separate containers that register over the shared bus).
DEFAULT_WORKER_BRAINS: list[type[BaseBrain]] = [
    VentureBrain,
    CommanderBrain,
    CapitalBrain,
]


class Harness:
    """The composed, runnable harness application context."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Construct (but do not start) the harness.

        Args:
            settings: Optional settings override; defaults to environment config.
        """
        self.settings = settings or get_settings()
        configure_logging(self.settings.log_level)

        audit_store = (
            SupabaseAuditStore(self.settings.supabase_url, self.settings.supabase_key)
            if self.settings.supabase_enabled
            else InMemoryAuditStore()
        )
        self.observer = Observer(audit_store)
        self.bus = build_message_bus(
            redis_url=self.settings.redis_url,
            use_in_memory=self.settings.use_in_memory_bus,
        )
        self.registry = build_registry(
            redis_url=self.settings.redis_url,
            use_in_memory=self.settings.use_in_memory_bus,
        )
        self.memory = build_shared_memory(self.settings, self.observer)
        self.llm = build_llm_client(self.settings)

        self.runtime = BrainRuntime(
            bus=self.bus,
            registry=self.registry,
            memory=self.memory,
            observer=self.observer,
            llm=self.llm,
            settings=self.settings,
        )
        self.ckos = CKOSBrain(self.runtime)
        self.workers: list[BaseBrain] = [cls(self.runtime) for cls in DEFAULT_WORKER_BRAINS]
        self._serve_tasks: list[asyncio.Task] = []
        self._background: set[asyncio.Task] = set()
        self._pipelines: dict[str, dict] = {}
        self._started = False

    async def startup(self) -> None:
        """Connect infrastructure, register brains, and start serve loops."""
        if self._started:
            return
        await self.observer.connect()
        await self.bus.connect()
        await self.registry.connect()
        await self.memory.connect()

        await self.ckos.register()
        for brain in self.workers:
            self._serve_tasks.append(asyncio.create_task(brain.serve()))

        # Give worker serve loops a moment to register before first pipeline.
        await asyncio.sleep(0.05)
        self._started = True
        logger.info(
            "harness_started",
            environment=self.settings.environment,
            in_memory=self.settings.use_in_memory_bus,
            brains=[b.brain_id for b in self.workers],
        )

    async def shutdown(self) -> None:
        """Stop serve loops and close all infrastructure connections."""
        for brain in self.workers:
            brain.stop()
        for task in self._serve_tasks:
            task.cancel()
        for task in self._serve_tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._serve_tasks.clear()

        await self.memory.close()
        await self.registry.close()
        await self.bus.close()
        await self.observer.close()
        self._started = False
        logger.info("harness_stopped")

    def spawn_pipeline(self, idea: str, context_id: str) -> asyncio.Task:
        """Launch a pipeline as a tracked background task and return it.

        Args:
            idea: The operator's idea/intent.
            context_id: The pipeline run identifier.

        Returns:
            The created :class:`asyncio.Task`.
        """
        task = asyncio.create_task(self.run_pipeline(idea, context_id=context_id))
        self._background.add(task)
        task.add_done_callback(self._background.discard)
        return task

    def track_pipeline(self, context_id: str, idea: str) -> None:
        """Register a pipeline id so it appears in the live pipeline view.

        Args:
            context_id: The pipeline run identifier.
            idea: The originating operator idea.
        """
        self._pipelines[context_id] = {
            "pipeline_id": context_id,
            "idea": idea,
            "status": "running",
        }

    def list_pipelines(self) -> list[dict]:
        """Return the most recent pipelines, newest first."""
        return list(reversed(list(self._pipelines.values())))

    async def get_pipeline(self, context_id: str) -> dict | None:
        """Return the current state of a pipeline from working memory.

        Args:
            context_id: The pipeline run identifier.

        Returns:
            A dict with the idea, plan, output, and status, or ``None`` if the
            pipeline id is unknown.
        """
        if context_id not in self._pipelines:
            return None
        working = await self.memory.context_store.get_all(context_id)
        return {
            "pipeline_id": context_id,
            "idea": working.get("idea", self._pipelines[context_id]["idea"]),
            "plan": working.get("plan", []),
            "history": working.get("history", []),
            "output": working.get("output", ""),
            "status": working.get("status", self._pipelines[context_id]["status"]),
        }

    async def run_pipeline(self, idea: str, *, context_id: str | None = None) -> PipelineRun:
        """Run a full pipeline for an operator idea.

        Args:
            idea: The operator's idea/intent.
            context_id: Optional explicit pipeline id; generated if omitted.

        Returns:
            The completed :class:`PipelineRun`.
        """
        if not self._started:
            await self.startup()
        cid = context_id or str(uuid.uuid4())
        if cid not in self._pipelines:
            self.track_pipeline(cid, idea)
        router = PipelineRouter(
            bus=self.bus,
            memory=self.memory,
            observer=self.observer,
            orchestrator=self.ckos,
        )
        run = await router.run(idea, cid, source="intake")
        self._pipelines[cid]["status"] = run.status
        return run
