# Blvckshell Agent Harness

> A personal AI operating system. Not a SaaS product, not a chatbot, not a wrapper
> around LangChain. A flawless agent orchestration engine that turns ideas into
> executed realities through a federation of specialized AI brains.

The harness is the nervous system of an autonomous organization. Every brain is a
specialist. The harness is what makes them one.

```
┌─────────────────────────────────────────┐
│           INTAKE INTERFACE              │  ← Voice / text / API idea capture
├─────────────────────────────────────────┤
│              CKOS ROUTER                │  ← Understands intent, decomposes, routes
├─────────────────────────────────────────┤
│            MESSAGE BUS                  │  ← All brains communicate through here
├─────────────────────────────────────────┤
│          BRAIN REGISTRY                 │  ← Brains register, advertise capabilities
├─────────────────────────────────────────┤
│         SHARED MEMORY LAYER             │  ← Judgment Ledger, context, doctrine
├─────────────────────────────────────────┤
│        OBSERVER / AUDIT LOG             │  ← Every message, decision, outcome logged
└─────────────────────────────────────────┘
```

## Spin up the full stack in one command

```bash
docker compose -f docker/docker-compose.yml up --build
```

This brings up Redis, the harness API (with the full brain federation running over
the bus), and the Next.js command interface:

- Harness API → http://localhost:8000  (docs at `/docs`)
- Command interface → http://localhost:3000

It works out of the box with **zero secrets**: the default inference provider is a
deterministic offline stub, the message bus and persistence fall back to in-process
implementations. Add credentials (below) to switch on Claude, Redis, and Supabase.

## Run the backend without Docker

```bash
pip install --user poetry        # if you don't have it
poetry install                   # install dependencies
poetry run uvicorn harness.api.main:app --reload   # serve on :8000
# or: poetry run blvckshell-harness
```

Drop an idea and watch the pipeline run:

```bash
curl -s -X POST 'http://localhost:8000/intake?wait=true' \
  -H 'content-type: application/json' \
  -d '{"text": "I want to build a trading AI that outperforms the market"}' | jq
```

## The test that proves it works

```bash
poetry run pytest -q                     # full suite
poetry run pytest tests/test_pipeline_e2e.py -q   # the end-to-end pipeline
```

`tests/test_pipeline_e2e.py` runs the canonical scenario: an idea goes in, CKOS
decomposes it and routes to the Venture, Commander, and Capital brains, each
executes and logs a judgment, CKOS aggregates, and the observer captures the full
trace. If this passes, the harness is real.

## Configuration

Copy `.env.example` to `.env`. Every value has a safe in-process default, so the
file can be left blank. Highlights (all prefixed `BLVCKSHELL_`):

| Variable | Default | Effect |
|----------|---------|--------|
| `INFERENCE_PROVIDER` | `stub` | `stub` (offline) · `anthropic` · `ollama` |
| `ANTHROPIC_API_KEY` | — | Required for the `anthropic` provider (Claude). |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | localhost / `qwen2.5:14b` | Local Qwen via Ollama. |
| `REDIS_URL` | — | Set to use the Redis message bus + working memory. |
| `SUPABASE_URL` / `SUPABASE_KEY` | — | Set to persist memory in Supabase. |
| `INPROCESS_BRAINS` | `true` | `false` runs brains as standalone containers. |

### Persistence (Supabase)

Apply `scripts/schema.sql` to your Supabase project, set the env vars, then seed
founding doctrine:

```bash
poetry run blvckshell-seed
```

## Project layout

```
harness/        Core engine: schemas, message bus, router, registry, memory,
                observer, agent loop, inference, FastAPI app.
brains/         Each brain, isolated. _base/ is the plugin contract; ckos/ is the
                orchestrator; venture/, commander/, capital/ are specialists.
memory/         Working context, episodic, doctrine stores, and the Judgment Ledger.
intake/         Text / voice / API idea capture.
docker/         Compose + Dockerfiles (harness and one-brain-per-container).
scripts/        seed_db, register_brain, Supabase schema.
docs/           architecture · message_protocol · brain_sdk.
tests/          Pytest suite (unit + end-to-end pipeline).
frontend/       Next.js 14 command interface.
```

## Build a new brain

Extend `LLMWorkerBrain`, declare capabilities, register it. See
[`docs/brain_sdk.md`](docs/brain_sdk.md). The message protocol is documented in
[`docs/message_protocol.md`](docs/message_protocol.md) and the system design in
[`docs/architecture.md`](docs/architecture.md).

## Quality bar

- Type hints and docstrings throughout; async end to end.
- Secrets via environment variables only — never hardcoded.
- A brain failing never crashes the harness.
- `ruff` clean; 50+ tests; the core is covered and the full pipeline is tested.

```bash
poetry run ruff check .
poetry run pytest --cov
```
