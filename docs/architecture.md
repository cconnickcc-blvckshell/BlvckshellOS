# Blvckshell Harness — Architecture

The harness is the nervous system of an autonomous organization. Every brain is a
specialist; the harness is what makes them one.

## The six layers

```
┌─────────────────────────────────────────┐
│           INTAKE INTERFACE              │  intake/  — voice / text / API capture
├─────────────────────────────────────────┤
│              CKOS ROUTER                │  brains/ckos + harness/core/router
├─────────────────────────────────────────┤
│              MESSAGE BUS                │  harness/core/message_bus
├─────────────────────────────────────────┤
│            BRAIN REGISTRY              │  harness/core/registry
├─────────────────────────────────────────┤
│          SHARED MEMORY LAYER           │  harness/core/memory + memory/
├─────────────────────────────────────────┤
│         OBSERVER / AUDIT LOG           │  harness/core/observer
└─────────────────────────────────────────┘
```

These are composed by `harness/core/harness.py` (`Harness`), and exposed over
HTTP by `harness/api/main.py`.

## The agent loop (per brain)

`harness/core/agent_loop.py` implements the cycle every brain runs for one task:

```
RECEIVE TASK → LOAD CONTEXT → THINK (LLM) → ACT (tools) → OBSERVE (results)
            → ITERATE until done → EMIT RESULT → LOG TO JUDGMENT LEDGER
```

The loop is model-agnostic (it talks only to an `LLMClient` and a list of
`BaseTool`) and reports every LLM/tool call to the Observer.

## A pipeline run, end to end

1. **Intake** receives an idea (`POST /intake`) and assigns a `context_id`.
2. **CKOS** (`plan`) decomposes the idea into `Task`s and routes each to a
   registered brain — never to a capability that is not advertised.
3. The **PipelineRouter** dispatches tasks onto the **bus** in dependency-ordered
   waves, using a unique reply address `pipeline:<context_id>`.
4. Each **brain** loads context from **shared memory**, runs the **agent loop**,
   logs a **Judgment Ledger** entry, and emits a `Result` back over the bus.
5. **CKOS** (`synthesize`) aggregates the results into one coherent briefing.
6. The **Observer** records every message, decision, and outcome throughout.

## Shared memory tiers

| Tier            | Backend                  | Lifetime        | Module                     |
|-----------------|--------------------------|-----------------|----------------------------|
| Working memory  | Redis (hash, TTL 24h)    | per pipeline    | `memory/context_store.py`  |
| Episodic memory | Supabase (`judgment_ledger`) | permanent   | `memory/judgment_ledger.py`|
| Doctrine        | Supabase (`doctrine`)    | append-only     | `memory/doctrine_store.py` |

A correct, high-confidence belief (≥ 0.8) is eligible for promotion from the
ledger to doctrine via `SharedMemory.promote_to_doctrine`.

## Deployment topologies

- **Single process (default):** `run_workers_in_process=true`. CKOS and all
  brains run inside the harness process. One `docker compose up`.
- **Distributed:** `run_workers_in_process=false`. Each brain runs in its own
  container (`scripts/run_brain.py`, `docker/Dockerfile.brain`) against a shared
  Redis bus + registry. Because everything communicates over the bus
  abstraction, no code changes are needed to move between topologies.

## Offline mode

With no Anthropic key (or `use_fake_llm=true`) the harness uses a deterministic
`FakeLLMClient`; with `use_in_memory_bus=true` it uses in-process bus/memory.
The full pipeline — including the end-to-end test — runs with zero external
infrastructure.
