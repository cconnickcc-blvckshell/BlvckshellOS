# Blvckshell Agent Harness

> A personal AI operating system. Not a chatbot, not a LangChain wrapper — a
> flawless agent orchestration engine that turns ideas into executed realities
> through a federation of specialized AI brains.

The harness is the nervous system of an autonomous organization. Every brain is a
specialist. The harness is what makes them one.

## Spin up the full stack in one command

```bash
docker compose -f docker/docker-compose.yml up --build
```

This brings up Redis, the harness API (`http://localhost:8000`), and the command
interface (`http://localhost:3000`). No API keys are required — without an
Anthropic key the harness runs on a deterministic offline LLM so you can see the
whole machine work immediately. Add keys in `.env` (see `.env.example`) to switch
on real inference and persistence.

## Run it locally (no Docker)

```bash
# 1. Install dependencies (Poetry)
poetry install

# 2. Run fully offline (in-memory bus/memory + deterministic LLM)
BLVCKSHELL_USE_IN_MEMORY_BUS=true BLVCKSHELL_USE_FAKE_LLM=true \
  poetry run blvckshell-harness
# → http://localhost:8000/docs
```

Drop an idea and watch a pipeline run:

```bash
curl -s -X POST http://localhost:8000/intake \
  -H 'content-type: application/json' \
  -d '{"text":"I want to build a trading AI that outperforms the market","wait":true}' | jq .
```

CKOS decomposes the idea, routes it to the Venture, Commander, and Capital
brains, each executes and logs a judgment, and CKOS synthesizes a final briefing
— with the Observer capturing the full trace.

## The test that proves it works

```bash
poetry run pytest        # 60 tests, 89% coverage
poetry run ruff check .  # lint
```

`tests/test_pipeline_e2e.py` runs the canonical proof end to end: idea in →
CKOS routes → brains execute → results back → judgments logged → coherent output
out, with a full Observer trace. It also proves a failing brain never crashes the
harness.

## Architecture

Six layers, composed by `harness/core/harness.py`:

```
INTAKE  →  CKOS ROUTER  →  MESSAGE BUS  →  BRAIN REGISTRY  →  SHARED MEMORY  →  OBSERVER
```

- **Message protocol** — `harness/schemas/` (`HarnessMessage`, `Task`, `Result`,
  `JudgmentEntry`, …). Strict Pydantic v2; the foundation everything builds on.
- **Message bus** — `harness/core/message_bus.py`. Redis pub/sub + durable
  queues, with an in-memory implementation for tests/offline.
- **Shared memory** — three tiers: working memory (Redis), Judgment Ledger and
  Doctrine Store (Supabase). See `harness/core/memory.py`, `memory/`.
- **Registry** — `harness/core/registry.py`. Capability discovery + heartbeats.
- **Observer** — `harness/core/observer.py`. Audits everything; live SSE stream.
- **Agent loop** — `harness/core/agent_loop.py`. The think/act/observe cycle.
- **CKOS** — `brains/ckos/`. The conductor: decompose, route, synthesize.

Deep dives: [`docs/architecture.md`](docs/architecture.md),
[`docs/message_protocol.md`](docs/message_protocol.md),
[`docs/brain_sdk.md`](docs/brain_sdk.md).

## Adding a brain

Extend `LLMBrain`, declare `capabilities` and a `system_prompt`, register it, and
run. CKOS discovers and routes to it automatically. Full guide in
[`docs/brain_sdk.md`](docs/brain_sdk.md).

## HTTP API

| Method | Path                       | Purpose                                  |
|--------|----------------------------|------------------------------------------|
| POST   | `/intake`                  | Submit a text idea (`wait` to block).    |
| POST   | `/intake/voice`            | Submit base64 audio (transcribe → run).  |
| GET    | `/pipelines`               | List recent pipelines.                   |
| GET    | `/pipelines/{id}`          | Live state of one pipeline.              |
| GET    | `/brains`                  | Registered brains + live state (orbs).   |
| GET    | `/ledger`                  | Judgment Ledger entries.                 |
| GET    | `/doctrine`                | Promoted doctrine.                       |
| GET    | `/observer/events`         | Recent audit events.                     |
| GET    | `/observer/stream`         | Live audit stream (SSE).                 |

## Configuration

All config is environment-driven (prefix `BLVCKSHELL_`); see `.env.example`.
Nothing is hardcoded. Notable flags:

- `BLVCKSHELL_USE_IN_MEMORY_BUS` — run without Redis.
- `BLVCKSHELL_USE_FAKE_LLM` — deterministic offline inference.
- `BLVCKSHELL_RUN_WORKERS_IN_PROCESS` — single-process vs. distributed brains.

## Persistence

For durable memory, set `BLVCKSHELL_SUPABASE_URL`/`KEY` and apply the schema:

```bash
poetry run python -m scripts.seed_db          # print schema SQL
poetry run python -m scripts.seed_db --check  # verify connectivity
```

## Command interface

The Next.js command interface (`frontend/`) is a dark, precise, alive command
center: Intake, live Pipeline view with breathing brain orbs, the Judgment
Ledger, Doctrine, and the real-time Observer stream. See `frontend/README.md`.

## Project layout

```
harness/     core engine (schemas, bus, router, registry, memory, observer, agent loop, API)
brains/      _base contract + CKOS + example specialist brains
memory/      context store, judgment ledger, doctrine store
intake/      text / voice / API intake
frontend/    Next.js command interface
docker/      Dockerfiles, compose, Supabase schema
scripts/     run_brain, seed_db, register_brain
docs/        architecture, message protocol, brain SDK
```
