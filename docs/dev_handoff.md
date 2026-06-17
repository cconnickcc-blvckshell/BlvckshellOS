# Developer Handoff

Everything a new engineer needs to be productive on the Blvckshell harness. Read
[`architecture.md`](architecture.md) first for the mental model, then this.

---

## 1. TL;DR

- **What it is:** a personal AI operating system that turns an operator's idea
  into an executed run across a federation of specialist "brains".
- **The contract is the harness.** Brains are plugins. Adding a brain is a config
  change, never an edit to `harness/core/harness.py`.
- **It runs with zero credentials:** in-memory bus/memory + a deterministic fake
  LLM. Add Redis/Supabase/Anthropic via env to scale up.

---

## 2. Get running in 60 seconds

```bash
# Option A — full stack (Redis + harness + UI)
docker compose -f docker/docker-compose.yml up --build
#   API → http://localhost:8000/docs   UI → http://localhost:3000

# Option B — Python only, fully offline
python -m venv .venv && . .venv/bin/activate
pip install -e .            # or: poetry install
BLVCKSHELL_USE_IN_MEMORY_BUS=true BLVCKSHELL_USE_FAKE_LLM=true \
  uvicorn harness.api.main:app --port 8000
```

Smoke test:

```bash
curl -s -X POST localhost:8000/intake \
  -H 'content-type: application/json' \
  -d '{"text":"build a trading AI that beats the market","wait":true}' | jq .
```

---

## 3. Test & lint

```bash
pytest                 # 82 tests, ~90% coverage (>= 85% required)
pytest tests/test_sub_agent.py -q     # one area
ruff check .           # must be clean
```

The suite runs fully offline. `conftest.py` provides an `harness` fixture wired
to in-memory backends + the fake LLM.

> Note: voice intake uses `python-multipart` only if you exercise file-upload
> form routes; the default base64 voice path and all core tests do not need it.

---

## 4. Mental model in five sentences

1. An **Objective** (operator intent) gets one or more **Runs**; a Run is
   decomposed into **Tasks**; a Task may spawn **AgentCalls** (sub-agents).
2. The **Orchestrator** (`harness/core/orchestrator.py`) plans and synthesizes —
   it is harness-internal plumbing, **not** a brain, and never registers.
3. The **PipelineRouter** dispatches Tasks over the **MessageBus** in
   dependency-ordered waves and collects results on `pipeline:<run_id>`.
4. A **Brain** loads context, runs the **AgentLoop** (think/act/observe), may
   `spawn_agent`, logs a **JudgmentEntry**, and emits a **Result**.
5. The **Observer** records every event; **SharedMemory** holds working memory
   (Redis), the Judgment Ledger and Doctrine (Supabase).

---

## 5. How to extend

### Add a brain
1. Create `brains/<name>/brain.py` extending `LLMBrain` (set `brain_id`,
   `capabilities`, `system_prompt`; optionally `tools`).
2. Add `"brains.<name>.brain:<ClassName>"` to `BLVCKSHELL_WORKER_BRAIN_MODULES`.
3. Done — the Orchestrator discovers and routes to it. Full guide:
   [`brain_sdk.md`](brain_sdk.md).

### Add a tool
Use `FunctionTool(name, description, input_schema, func)` (an async fn) and add
it to a brain's `tools` list.

### Spawn a sub-agent
Call `await self.spawn_agent(capability=…, objective=…, parent_task_id=…,
run_id=…, objective_id=…)` inside `handle_task`; pull the ids from
`task.metadata`. See [`brain_sdk.md`](brain_sdk.md).

### Add an API endpoint
Add a route in `harness/api/main.py` (or a router under `intake/`).

---

## 6. Configuration (env, prefix `BLVCKSHELL_`)

| Key | Default | Effect |
|-----|---------|--------|
| `USE_IN_MEMORY_BUS` | `false` | In-process bus/memory/registry (no Redis). |
| `USE_FAKE_LLM` | `false` | Deterministic offline LLM. |
| `RUN_WORKERS_IN_PROCESS` | `true` | Single-process vs. distributed brains. |
| `WORKER_BRAIN_MODULES` | venture,commander,capital | Brains to load (`module:Class`). |
| `REDIS_URL` | `redis://localhost:6379/0` | Bus + working memory. |
| `SUPABASE_URL` / `SUPABASE_KEY` | — | Ledger/doctrine/audit persistence. |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` | — / sonnet | Real inference. |

Full list with descriptions: `.env.example` and `harness/config.py`.

---

## 7. Persistence

For durable memory set `SUPABASE_URL`/`KEY` and apply the schema:

```bash
python -m scripts.seed_db          # prints docker/supabase_schema.sql
python -m scripts.seed_db --check  # verifies connectivity
```

Tables: `judgment_ledger`, `doctrine`, `audit_log`.

---

## 8. Deployment topologies

- **Single process** (default): everything in the harness container.
- **Distributed**: set `RUN_WORKERS_IN_PROCESS=false`, run each brain via
  `python -m scripts.run_brain <id>` (or `docker/Dockerfile.brain`) against a
  shared Redis. No code changes required.

---

## 9. Gotchas & conventions

- **Don't import concrete brains in `harness/core/`** — only the abstract
  `BaseBrain`/`BrainRuntime` contract. Brains come from config.
- **External pipeline id == `objective_id`.** Internally, working memory,
  judgments, and observer events key on `run_id`.
- **A failing brain or sub-agent must never crash the harness** — failures are
  caught, audited, and returned as `FAILURE`/`AgentCall(status=FAILED)`.
- **All blocking I/O is async.** Redis/Supabase/Anthropic SDKs are imported lazily
  so the offline path needs none of them.
- **Schemas `message.py` and `judgment.py` are locked.** Add ancestry via
  `metadata`, not by changing the envelope.
- **Type hints + docstrings on every public function.** `ruff` enforces import
  order and style; keep it green.

---

## 10. Where things live (quick map)

```
harness/schemas/   contracts (HarnessMessage, Task, Result, Objective, Judgment, …)
harness/core/      engine (orchestrator, router, bus, registry, memory, observer,
                   agent_loop, llm, brain_loader, harness)
harness/api/       FastAPI app
brains/_base/      BaseBrain + tools (the plugin contract, incl. spawn_agent)
brains/examples/   Venture, Commander, Capital
memory/            context / judgment-ledger / doctrine backends
intake/            text / voice / API capture
scripts/           run_brain, seed_db, register_brain
docker/            Dockerfiles, compose, Supabase schema
frontend/          Next.js command interface
docs/              architecture, message_protocol, brain_sdk, workflows,
                   file_reference, system_graph, dev_handoff (this file)
```

---

## 11. Roadmap pointers (post-v2)

- **CKOS** — the intelligent brain that will sit *above* the harness and direct it
  (distinct from the internal Orchestrator).
- **Outcome learning** — wire `ledger.record_outcome(...)` into real-world result
  capture to drive doctrine promotion automatically.
- **Multi-run objectives** — the schema already supports many Runs per Objective;
  the harness currently keeps one Run per external id.
- **Richer sub-agent graphs** — nested spawning is supported; add depth/cycle
  guards and budget controls as usage grows.
