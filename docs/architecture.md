# Blvckshell Harness — Architecture

The harness is the nervous system of an autonomous organization. Every brain is a
specialist; the harness is what makes them one. **The harness is the contract.
Everything else is a plugin.**

## The six layers

```
┌─────────────────────────────────────────┐
│           INTAKE INTERFACE              │  intake/  — voice / text / API capture
├─────────────────────────────────────────┤
│              ORCHESTRATOR               │  harness/core/orchestrator.py (NOT a brain)
├─────────────────────────────────────────┤
│              MESSAGE BUS                │  harness/core/message_bus.py
├─────────────────────────────────────────┤
│            BRAIN REGISTRY              │  harness/core/registry.py
├─────────────────────────────────────────┤
│          SHARED MEMORY LAYER           │  harness/core/memory.py + memory/
├─────────────────────────────────────────┤
│         OBSERVER / AUDIT LOG           │  harness/core/observer.py
└─────────────────────────────────────────┘
```

These are composed by `harness/core/harness.py` (`Harness`) and exposed over HTTP
by `harness/api/main.py`. The mechanical routing engine
(`harness/core/router.py`, `PipelineRouter`) carries out the orchestrator's plan.

## The execution hierarchy (Objective → Run → Task → AgentCall)

The flat `context_id` of v1 is replaced by an explicit ancestry. Defined in
`harness/schemas/objective.py`:

```
Objective                       the operator's intent — stable, never changes
└── Run                         one execution attempt of the objective
    └── Task                    one unit of work within a run
        └── AgentCall           one sub-agent invocation spawned by a brain
```

| Entity     | Id field        | Parent reference(s)              |
|------------|-----------------|----------------------------------|
| Objective  | `objective_id`  | —                                |
| Run        | `run_id`        | `objective_id`                   |
| Task       | `id`/`task_id`  | `run_id`, `objective_id`         |
| AgentCall  | `agent_call_id` | `task_id`, `run_id`, `objective_id` |

Every `TASK` message carries its full ancestry in `HarnessMessage.metadata`
(`objective_id`, `run_id`, `task_id`), so any component — including a brain about
to spawn a sub-agent — can reconstruct exactly where it sits in the tree.

> The externally-visible "pipeline id" used by intake and the UI is the
> `objective_id`. Internally, working memory, judgments, and observer events are
> keyed on `run_id`.

## The Orchestrator is not a brain

`Orchestrator` (`harness/core/orchestrator.py`) is the harness's internal routing
engine. It **does not** extend `BaseBrain`, register with the registry, or appear
in the brain-orb view. It has two jobs:

- **`plan(objective, run)`** — decompose into `Task`s, validate every capability
  against the live registry (never route to an unregistered capability), fall
  back to a heuristic if the LLM is unavailable, and log the routing decision to
  the Judgment Ledger. Returned tasks have `run_id`/`objective_id` populated.
- **`synthesize(objective, run, results)`** — aggregate results into one briefing.

CKOS — a future *intelligent* brain that will sit **above** the harness and direct
it — is a different thing entirely and deliberately lives outside the harness.

## Dynamic brain loading

Brains are declared in configuration, not in code. `harness/core/brain_loader.py`
imports each `module:ClassName` listed in `BLVCKSHELL_WORKER_BRAIN_MODULES`.
Adding a brain is a config change; `harness/core/harness.py` has **zero
brain-specific imports**. Unimportable entries are logged and skipped so the
harness always starts.

## The agent loop (per brain)

`harness/core/agent_loop.py` implements the cycle every brain runs for one task:

```
RECEIVE TASK → LOAD CONTEXT → THINK (LLM) → ACT (tools) → OBSERVE (results)
            → ITERATE until done → EMIT RESULT → LOG TO JUDGMENT LEDGER
```

The loop is model-agnostic (it talks only to an `LLMClient` and a list of
`BaseTool`) and reports every LLM/tool call to the Observer.

## Sub-agent spawning (first-class)

`BaseBrain.spawn_agent(...)` lets **any** brain spawn a child agent for a
capability, await its result, and incorporate it. The sub-agent runs through the
same machinery (bus → registry routing → agent loop → judgment logging). A failed
spawn (no brain for the capability, or a timeout) returns an `AgentCall` with
`status=FAILED` and never crashes the parent or the harness. The Observer records
`AGENT_SPAWNED` and `AGENT_RETURNED`.

See [`workflows.md`](workflows.md) for the spawn sequence diagram.

## A pipeline run, end to end

1. **Intake** receives a statement (`POST /intake`) → an `Objective`.
2. The router opens a **Run** and asks the **Orchestrator** to `plan`.
3. The router dispatches tasks onto the **bus** in dependency-ordered waves, each
   message carrying full ancestry, using reply address `pipeline:<run_id>`.
4. Each **brain** loads context from **shared memory**, runs the **agent loop**,
   may **spawn sub-agents**, logs a **Judgment Ledger** entry, and emits a
   `Result` back over the bus.
5. The **Orchestrator** `synthesize`s the results into one briefing.
6. The **Observer** records every message, decision, and outcome throughout.

## Shared memory tiers

| Tier            | Backend                  | Lifetime        | Module                     |
|-----------------|--------------------------|-----------------|----------------------------|
| Working memory  | Redis (hash, TTL 24h)    | per run         | `memory/context_store.py`  |
| Episodic memory | Supabase (`judgment_ledger`) | permanent   | `memory/judgment_ledger.py`|
| Doctrine        | Supabase (`doctrine`)    | append-only     | `memory/doctrine_store.py` |
| Conversations   | Supabase / in-memory     | per session     | `memory/conversation_store.py` |

A correct, high-confidence belief (≥ 0.8) is eligible for promotion from the
ledger to doctrine via `SharedMemory.promote_to_doctrine`. Outcome capture closes
the learning loop: `POST /judgments/{id}/outcome` → belief update → doctrine
promotion or penalty.

## Judgment lifecycle (Phase 1 + 1b)

Every `LLMBrain` runs the nine-stage judgment cycle in `judgment/lifecycle.py`
before writing to the ledger. Models supply **evidence**, not decisions.

```
OBSERVATION → BELIEF → CONFIDENCE → CHALLENGE → EVIDENCE → FORECAST → DECISION → OUTCOME → LEARNING
                  ↑ case retrieval      ↑ J9           ↑ agent loop  ↑ J11 exploration
```

| Stage        | Module                              | Purpose                                      |
|--------------|-------------------------------------|----------------------------------------------|
| Confidence   | `judgment/stages/confidence.py`     | Doctrine + ledger outcome adjustment (J9)    |
| Exploration  | `judgment/stages/exploration.py`    | UCB bandit + opportunity cost signal (J11)   |
| Case recall  | `judgment/reasoning/case_retrieval.py` | Semantic-similarity lesson recall into Evidence (J12) |
| Learning     | `judgment/stages/learning.py`       | Post-outcome Bayesian belief update (J10)    |

Guards (authoritative, not observational):

- **Harm-aware** (`judgment/guards/harm_aware.py`) — capital domain; blocks
  `HOLD→PROCEED`, negative ROI, risk above cap, poor similar past outcomes.
- **Safe divergence** (`judgment/guards/safe_divergence.py`) — tension classes;
  allowlists `PROCEED→STAGED_PROCEED` and `STAGED_PROCEED→REQUEST_MORE_EVIDENCE`.

Every stage emits `consumed_signals` / `ignored_signals` to the Observer
(`JUDGMENT_STAGE_COMPLETED`). Algorithms must pass federation promotion gates in
`tests/simulation/` before promotion (divergence 10–30%, ROI Δ ≥ 1%, harm = 0).

See [`v2_incorporation_audit.md`](v2_incorporation_audit.md) for the full
incorporation tracker and [`archive/`](archive/) for read-only V1 reference docs.

## Deployment topologies

- **Single process (default):** `run_workers_in_process=true`. Brains run inside
  the harness process. One `docker compose up`.
- **Distributed:** `run_workers_in_process=false`. Each brain runs in its own
  container (`scripts/run_brain.py`, `docker/Dockerfile.brain`) against a shared
  Redis bus + registry. No code changes are needed to move between topologies.

## Offline mode

With no Anthropic key (or `use_fake_llm=true`) the harness uses a deterministic
`FakeLLMClient`; with `use_in_memory_bus=true` it uses in-process bus/memory/
registry. The full pipeline — including sub-agent spawning and the end-to-end
test — runs with zero external infrastructure.
