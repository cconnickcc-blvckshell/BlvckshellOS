"""The Harness — the application context that wires every layer together.

This is the nervous system. It constructs the message bus, registry, shared
memory, observer, and LLM client; loads the configured specialist brains
*dynamically* (no hardcoded imports); brings up the harness-internal
:class:`~harness.core.orchestrator.Orchestrator`; and exposes a single
:meth:`run_pipeline` entry point that intake calls.

Brains run in-process here by default (so a single ``docker compose up`` works),
but because everything communicates over the bus abstraction, brains can equally
run in their own containers against a shared Redis bus.

There are deliberately **zero brain-specific imports** in this module — brains
are declared in configuration and loaded by :mod:`harness.core.brain_loader`.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid

from brains._base.brain import BaseBrain, BrainRuntime

from harness.config import Settings, get_settings
from harness.core.brain_loader import instantiate_brains, load_brain_classes
from harness.core.llm import build_llm_client
from harness.core.memory import build_shared_memory
from harness.core.message_bus import build_message_bus
from harness.core.observer import (
    InMemoryAuditStore,
    Observer,
    SupabaseAuditStore,
)
from harness.core.orchestrator import Orchestrator
from harness.core.registry import build_registry
from harness.core.router import PipelineRouter
from harness.logging_config import configure_logging, get_logger
from harness.schemas.objective import Objective, Run

logger = get_logger("harness")


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

        # Dynamic brain loading — brains come from config, not hardcoded imports.
        brain_classes = load_brain_classes(self.settings.worker_brain_modules)
        self.workers: list[BaseBrain] = instantiate_brains(brain_classes, self.runtime)

        # The orchestrator is a harness-internal component, NOT a brain. It does
        # not extend BaseBrain and never registers with the registry.
        self.orchestrator = Orchestrator(
            llm=self.llm,
            registry=self.registry,
            memory=self.memory,
            observer=self.observer,
            model=self.settings.anthropic_model,
        )

        self._serve_tasks: list[asyncio.Task] = []
        self._background: set[asyncio.Task] = set()
        self._pipelines: dict[str, dict] = {}
        self._runs: dict[str, Run] = {}
        self._started = False

    async def startup(self) -> None:
        """Connect infrastructure and start the worker serve loops."""
        if self._started:
            return
        await self.observer.connect()
        await self.bus.connect()
        await self.registry.connect()
        await self.memory.connect()

        if self.settings.run_workers_in_process:
            for brain in self.workers:
                self._serve_tasks.append(asyncio.create_task(brain.serve()))
            # Give worker serve loops a moment to register before first pipeline.
            await asyncio.sleep(0.05)
        else:
            logger.info("harness_distributed_workers", note="workers run as separate processes")
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

    # -- pipeline tracking (external id == objective_id) -------------------

    def spawn_pipeline(self, statement: str, objective_id: str) -> asyncio.Task:
        """Launch a pipeline as a tracked background task and return it.

        Args:
            statement: The operator's idea/intent.
            objective_id: The externally-visible pipeline id (the objective id).

        Returns:
            The created :class:`asyncio.Task`.
        """
        task = asyncio.create_task(self.run_pipeline(statement, objective_id=objective_id))
        self._background.add(task)
        task.add_done_callback(self._background.discard)
        return task

    def track_pipeline(self, objective_id: str, statement: str) -> None:
        """Register a pipeline so it appears in the live pipeline view.

        Args:
            objective_id: The externally-visible pipeline id.
            statement: The originating operator idea.
        """
        self._pipelines[objective_id] = {
            "pipeline_id": objective_id,
            "idea": statement,
            "status": "running",
        }

    def list_pipelines(self) -> list[dict]:
        """Return the most recent pipelines, newest first."""
        return list(reversed(list(self._pipelines.values())))

    async def get_pipeline(self, objective_id: str) -> dict | None:
        """Return the current state of a pipeline by its external id.

        Args:
            objective_id: The externally-visible pipeline id.

        Returns:
            A dict with the idea, plan, history, output, and status, or ``None``
            if the id is unknown.
        """
        if objective_id not in self._pipelines:
            return None
        stub = self._pipelines[objective_id]
        run = self._runs.get(objective_id)
        if run is None:
            return {
                "pipeline_id": objective_id,
                "idea": stub["idea"],
                "plan": [],
                "history": [],
                "output": "",
                "status": stub["status"],
            }
        return {
            "pipeline_id": objective_id,
            "run_id": run.run_id,
            "idea": stub["idea"],
            "plan": [t.model_dump(mode="json") for t in run.tasks],
            "history": [{"brain": r.brain_id, "summary": r.summary} for r in run.results],
            "output": run.output,
            "status": run.status.value,
        }

    async def run_pipeline(
        self,
        statement: str,
        *,
        objective_id: str | None = None,
        context_id: str | None = None,
    ) -> Run:
        """Accept a natural-language statement and run it as an Objective.

        Args:
            statement: The operator's idea/intent.
            objective_id: Optional explicit objective id (the external pipeline id).
            context_id: Legacy alias for ``objective_id`` (kept for the intake
                layer, which is intentionally untouched by this refactor).

        Returns:
            The completed :class:`Run`.
        """
        if not self._started:
            await self.startup()
        oid = objective_id or context_id or str(uuid.uuid4())
        if oid not in self._pipelines:
            self.track_pipeline(oid, statement)

        objective = Objective(objective_id=oid, statement=statement)
        router = PipelineRouter(
            bus=self.bus,
            memory=self.memory,
            observer=self.observer,
            orchestrator=self.orchestrator,
        )
        run = await router.run(objective, source="intake")
        self._runs[oid] = run
        self._pipelines[oid]["status"] = run.status.value
        return run
