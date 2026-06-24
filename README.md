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

The orchestrator decomposes the idea, routes it to the Venture, Commander, and
Capital brains, each executes and logs a judgment, and the orchestrator
synthesizes a final briefing — with the Observer capturing the full trace.

## The test that proves it works

```bash
poetry run pytest        # 156 tests, 84% coverage
poetry run ruff check .  # lint
```

`tests/test_pipeline_e2e.py` runs the canonical proof end to end: idea in →
orchestrator routes → brains execute → results back → judgments logged →
coherent output out, with a full Observer trace under a correct Objective → Run →
Task hierarchy. `tests/test_sub_agent.py` proves a brain can spawn a sub-agent
and use its result; other suites prove dynamic loading and that a failing brain
never crashes the harness.

## Architecture

Six layers, composed by `harness/core/harness.py`:

```
INTAKE  →  ORCHESTRATOR  →  MESSAGE BUS  →  BRAIN REGISTRY  →  SHARED MEMORY  →  OBSERVER
```

Work is tracked through an explicit hierarchy: **Objective → Run → Task →
AgentCall** (`harness/schemas/objective.py`).

- **Message protocol** — `harness/schemas/` (`HarnessMessage`, `Task`, `Result`,
  `Objective`/`Run`/`AgentCall`, `JudgmentEntry`, …). Strict Pydantic v2.
- **Orchestrator** — `harness/core/orchestrator.py`. The harness-internal routing
  engine: decompose, route (only to registered capabilities), synthesize. **Not a
  brain** — it never registers. (CKOS, a future intelligent brain *above* the
  harness, is a separate thing.)
- **Message bus** — `harness/core/message_bus.py`. Redis pub/sub + durable
  queues, with an in-memory implementation for tests/offline.
- **Shared memory** — three tiers: working memory (Redis), Judgment Ledger and
  Doctrine Store (Supabase). See `harness/core/memory.py`, `memory/`.
- **Registry** — `harness/core/registry.py`. Capability discovery + heartbeats.
- **Observer** — `harness/core/observer.py`. Audits everything; live SSE stream.
- **Agent loop** — `harness/core/agent_loop.py`. The think/act/observe cycle.
- **Sub-agents** — `BaseBrain.spawn_agent(...)`. Any brain can spawn a child
  agent for a capability, await it, and use the result.
- **Freelance-agent brains** — `brains/blvckbot/` (Research, Proposal, Build,
  Ops). A dedicated flow, separate from generic intake routing
  (`pipeline_participant = False`), that finds leads, drafts proposals, does
  the work, and flags financial/account actions for a human — every
  consequential step is forced through the `human_gate` guard
  (`judgment/guards/human_gate.py`), which downgrades `PROCEED`/
  `STAGED_PROCEED` to `REQUEST_MORE_EVIDENCE` so nothing executes
  unsupervised. Upwork access goes through `integrations/upwork_client.py`;
  Fiverr has no API, so leads only ever arrive via human paste-in
  (`POST /leads/fiverr`) — never scraped.

Deep dives:
[`docs/architecture.md`](docs/architecture.md) ·
[`docs/workflows.md`](docs/workflows.md) (wireframes, sequence diagrams, API) ·
[`docs/system_graph.md`](docs/system_graph.md) (full graph) ·
[`docs/file_reference.md`](docs/file_reference.md) (file purposes & deps) ·
[`docs/message_protocol.md`](docs/message_protocol.md) ·
[`docs/brain_sdk.md`](docs/brain_sdk.md) ·
[`docs/dev_handoff.md`](docs/dev_handoff.md).

## Adding a brain

Extend `LLMBrain`, declare `capabilities` and a `system_prompt`, then add its
`module:ClassName` to `BLVCKSHELL_WORKER_BRAIN_MODULES` — no harness code change.
The Orchestrator discovers and routes to it automatically. Full guide in
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
| GET    | `/approvals`               | NEEDS_OPERATOR queue awaiting a human.   |
| GET    | `/leads`                   | Manually submitted leads, newest first.  |
| POST   | `/leads/fiverr`            | Paste in a Fiverr listing to score it.   |

## Configuration

All config is environment-driven (prefix `BLVCKSHELL_`); see `.env.example`.
Nothing is hardcoded. Notable flags:

- `BLVCKSHELL_USE_IN_MEMORY_BUS` — run without Redis.
- `BLVCKSHELL_USE_FAKE_LLM` — deterministic offline inference.
- `BLVCKSHELL_RUN_WORKERS_IN_PROCESS` — single-process vs. distributed brains.
- `BLVCKSHELL_WORKER_BRAIN_MODULES` — which brains to load (`module:ClassName`).

## Persistence

For durable memory, set `BLVCKSHELL_SUPABASE_URL`/`KEY` and apply the schema:

```bash
poetry run python -m scripts.seed_db          # print schema SQL
poetry run python -m scripts.seed_db --check  # verify connectivity
```

## Command interface

The Next.js command interface (`frontend/`) is a dark, precise, alive command
center: Intake, live Pipeline view with breathing brain orbs, the Judgment
Ledger, Doctrine, the real-time Observer stream, and Leads & Approvals (the
Fiverr paste-in form and the NEEDS_OPERATOR confirm/reject queue). See
`frontend/README.md`.

## Project layout

```
harness/       core engine (schemas, orchestrator, router, bus, registry, memory, observer, agent loop, brain_loader, API)
brains/        _base contract (incl. spawn_agent) + example specialist brains + blvckbot (freelance-agent brains)
integrations/  external service clients (Upwork)
memory/        context store, judgment ledger, doctrine store
intake/        text / voice / API intake
frontend/      Next.js command interface
docker/        Dockerfiles, compose, Supabase schema
scripts/       run_brain, seed_db, register_brain
docs/          architecture, workflows, system_graph, file_reference, message_protocol, brain_sdk, dev_handoff
```
