# File Reference — Purposes & Dependencies

Every source file in the harness, what it does, and what it depends on. "Depends
on" lists the significant internal modules a file imports (external libs noted
where relevant).

---

## `harness/schemas/` — the contracts (no internal deps; safe to import anywhere)

| File | Purpose | Depends on |
|------|---------|-----------|
| `message.py` | `HarnessMessage` + `MessageType`. The universal envelope; wire (de)serialization and `reply()`. **Locked.** | pydantic |
| `task.py` | `Task` + `TaskStatus`. A unit of work; carries `run_id`/`objective_id` and a `task_id` alias. | pydantic |
| `result.py` | `Result` + `ResultStatus`. A brain's task outcome. | pydantic |
| `judgment.py` | `JudgmentEntry`. Belief + evidence + outcome. **Locked v1.** | pydantic |
| `objective.py` | `Objective`, `Run`, `RunStatus`, `AgentCall`. The execution hierarchy. | `task.py`, `result.py` |
| `brain_info.py` | `BrainInfo` (registry record), `BrainContext` (loaded context), `BrainState` (orb states). | `judgment.py` |
| `audit.py` | `AuditEvent` + `AuditEventType` (incl. `AGENT_SPAWNED`/`AGENT_RETURNED`). | pydantic |
| `__init__.py` | Re-exports all schemas for `from harness.schemas import …`. | all of the above |

---

## `harness/core/` — the engine

| File | Purpose | Depends on |
|------|---------|-----------|
| `harness.py` | `Harness`: composes every layer, dynamically loads brains, owns the Orchestrator, exposes `run_pipeline`. **Zero brain-specific imports.** | config, llm, memory, message_bus, observer, orchestrator, registry, router, brain_loader, schemas/objective, `brains._base.brain` (contract only) |
| `orchestrator.py` | `Orchestrator`: `plan()` + `synthesize()`. Harness-internal; **not a brain**. | llm, memory, observer, registry, orchestrator_prompts, schemas |
| `orchestrator_prompts.py` | System/planning/synthesis prompt templates for the Orchestrator. | — |
| `router.py` | `PipelineRouter`: dispatches the plan in dependency waves, collects results, drives synthesis; injects ancestry metadata. | memory, message_bus, observer, orchestrator, schemas |
| `brain_loader.py` | `load_brain_classes()` / `instantiate_brains()`: import brains from config strings, failure-isolated. | `brains._base.brain`, logging |
| `message_bus.py` | `MessageBus` (abstract) + `InMemoryMessageBus` + `RedisMessageBus`. pub/sub + queues + observer mirror. | schemas/message, redis (lazy) |
| `registry.py` | `BrainRegistry` (abstract) + in-memory/Redis impls. Registration, heartbeat, `find_by_capability` (single best) + `find_all_by_capability`. | schemas/brain_info, redis (lazy) |
| `memory.py` | `SharedMemory`: facade over the three tiers; doctrine promotion; `load_context`. `build_shared_memory()`. | config, observer, schemas, `memory/*` |
| `observer.py` | `Observer` + `AuditStore` (in-memory/Supabase). Persists, logs, and live-streams audit events. | schemas/audit, logging, supabase (lazy) |
| `agent_loop.py` | `AgentLoop`: the think/act/observe cycle; audits every LLM/tool call. | llm, observer, `brains._base.tools`, schemas/audit |
| `llm.py` | `LLMClient` (abstract) + `AnthropicClient` + `OllamaClient` + `FakeLLMClient`; `build_llm_client()`. | logging, anthropic/httpx (lazy) |

---

## `harness/` — config, logging, API

| File | Purpose | Depends on |
|------|---------|-----------|
| `config.py` | `Settings` (pydantic-settings, `BLVCKSHELL_` env). Incl. `worker_brain_modules`, `run_workers_in_process`. `get_settings()` cached. | pydantic-settings |
| `logging_config.py` | structlog setup; `configure_logging()` / `get_logger()`. | structlog |
| `api/main.py` | FastAPI app: lifespan boots `Harness`; routes for intake/pipelines/brains/ledger/doctrine/observer + SSE. | harness.core.harness, intake.api, fastapi |

---

## `brains/` — the plugins

| File | Purpose | Depends on |
|------|---------|-----------|
| `_base/brain.py` | `BaseBrain` (contract + lifecycle + `spawn_agent`), `LLMBrain` (agent-loop worker), `BrainRuntime` (injected services). | harness.core.* , schemas, `_base/tools` |
| `_base/tools.py` | `BaseTool` (abstract) + `FunctionTool` (async-fn adapter). | — |
| `examples/venture.py` | `VentureBrain` — idea validation + a `feasibility_score` tool. | `_base/brain`, `_base/tools` |
| `examples/commander.py` | `CommanderBrain` — execution planning. | `_base/brain` |
| `examples/capital.py` | `CapitalBrain` — capital/financial stub. | `_base/brain` |

> `brains/ckos/` was **deleted** in the v2 refactor; the orchestrator now lives in
> `harness/core/orchestrator.py` and is not a brain.

---

## `memory/` — the three storage backends

| File | Purpose | Depends on |
|------|---------|-----------|
| `context_store.py` | Working memory (tier 1): `ContextStore` + in-memory/Redis. TTL hash per run. | schemas, redis (lazy) |
| `judgment_ledger.py` | Episodic memory (tier 2): `JudgmentLedger` + in-memory/Supabase. | schemas/judgment, supabase (lazy) |
| `doctrine_store.py` | Doctrine (tier 3): `DoctrineStore` + in-memory/Supabase. Append-only; supersede. | schemas/judgment, supabase (lazy) |

---

## `intake/` — idea capture (do-not-touch zone)

| File | Purpose | Depends on |
|------|---------|-----------|
| `text.py` | `normalize_text()` — sanitize raw operator text. | — |
| `voice.py` | `Transcriber` (abstract) + `Passthrough`/`Whisper`; `transcribe_to_idea()`. | `text.py`, whisper (lazy) |
| `api.py` | `create_intake_router()` — text/voice intake `APIRouter`; calls `harness.run_pipeline`. | intake.text, intake.voice, fastapi |

---

## `scripts/` — operational tooling

| File | Purpose | Depends on |
|------|---------|-----------|
| `run_brain.py` | Run a single brain in its own process (distributed mode). | harness.core.*, brains.examples.* |
| `seed_db.py` | Print/verify the Supabase schema. | config, supabase (lazy) |
| `register_brain.py` | Inspect the live registry (`list` / `show`). | config, registry |

---

## `docker/`, `frontend/`, `tests/`

- `docker/` — `Dockerfile.harness`, `Dockerfile.brain`, `docker-compose.yml`,
  `supabase_schema.sql`. One-command local stack.
- `frontend/` — Next.js 14 command interface (`app/`, `components/`, `lib/`).
  Talks to the API over `NEXT_PUBLIC_HARNESS_URL`. See `frontend/README.md`.
- `tests/` + `harness/tests/` — pytest suite. Highlights:
  `test_pipeline_e2e.py` (full hierarchy), `test_sub_agent.py` (spawning),
  `test_dynamic_loading.py`, `test_hierarchy.py`, `test_orchestrator*.py`.

---

## Dependency direction (no cycles)

```
schemas  ◄── memory, core/*, brains/*, intake/*   (leaf; depends on nothing internal)
core/llm, core/observer, core/message_bus, core/registry, core/memory
         ◄── core/agent_loop, core/orchestrator, core/router, brains/_base
brains/_base ◄── brains/examples/*, core/brain_loader
core/harness ◄── api/main, scripts/*
intake/* ◄── api/main
```

The orchestrator never imports the router; the router imports the orchestrator;
the harness imports both. Brains depend on `core` services but `core` depends only
on the abstract `BaseBrain` contract — never on a concrete brain.
