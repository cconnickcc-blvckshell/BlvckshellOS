# Workflows, Connections & API Reference

Wireframe-level views of how data moves through the harness, the connections
between components, and the full HTTP API. Mermaid diagrams render on GitHub.

---

## 1. Component connection map

```mermaid
flowchart TB
    subgraph Client
        UI[Next.js Command Interface]
        CLI[curl / API client]
    end

    subgraph HarnessProcess["Harness process (harness/core/harness.py)"]
        API[FastAPI app\nharness/api/main.py]
        INTAKE[Intake router\nintake/api.py]
        ROUTER[PipelineRouter\nharness/core/router.py]
        ORCH[Orchestrator\nharness/core/orchestrator.py]
        REG[BrainRegistry]
        OBS[Observer]
        MEM[SharedMemory]
        BUS[MessageBus]
        subgraph Workers["Worker brains (dynamically loaded)"]
            B1[VentureBrain]
            B2[CommanderBrain]
            B3[CapitalBrain]
        end
        LLM[LLMClient\nAnthropic / Ollama / Fake]
    end

    subgraph Infra["Infrastructure (optional)"]
        REDIS[(Redis\nbus + working memory)]
        SUPA[(Supabase\nledger + doctrine + audit)]
        ANTH[(Anthropic API)]
    end

    UI --> API
    CLI --> API
    API --> INTAKE
    INTAKE --> ROUTER
    ROUTER --> ORCH
    ROUTER <--> BUS
    ORCH --> REG
    ORCH --> LLM
    ORCH --> MEM
    B1 & B2 & B3 <--> BUS
    B1 & B2 & B3 --> LLM
    B1 & B2 & B3 --> MEM
    B1 & B2 & B3 --> REG
    ROUTER --> OBS
    B1 & B2 & B3 --> OBS
    ORCH --> OBS
    BUS -.-> REDIS
    MEM -.-> REDIS
    MEM -.-> SUPA
    OBS -.-> SUPA
    LLM -.-> ANTH
```

`-.->` edges are optional backends; with the in-memory/fake defaults the whole
graph runs in one process with no external infrastructure.

---

## 2. Workflow: idea → executed run

```mermaid
sequenceDiagram
    actor Operator
    participant API as FastAPI / Intake
    participant H as Harness
    participant R as PipelineRouter
    participant O as Orchestrator
    participant Reg as Registry
    participant Bus as MessageBus
    participant Br as Brain(s)
    participant Mem as SharedMemory
    participant Obs as Observer

    Operator->>API: POST /intake {text}
    API->>H: run_pipeline(statement)
    H->>R: run(Objective)
    R->>Obs: PIPELINE_STARTED (run_id)
    R->>O: plan(objective, run)
    O->>Reg: list_all() (valid capabilities)
    O->>O: LLM plan → validate → (heuristic fallback)
    O->>Mem: record routing JudgmentEntry
    O-->>R: [Task] (run_id, objective_id set)
    loop dependency-ordered waves
        R->>Bus: enqueue TASK (ancestry in metadata)
        R->>Obs: MESSAGE_SENT
        Bus->>Br: dequeue TASK
        Br->>Mem: load_context(run_id)
        Br->>Br: AgentLoop think/act/observe
        Br->>Obs: LLM_CALL / TOOL_CALL
        Br->>Mem: record JudgmentEntry
        Br->>Bus: enqueue RESULT → pipeline:<run_id>
        Bus-->>R: dequeue RESULT
        R->>Obs: MESSAGE_RECEIVED
    end
    R->>O: synthesize(objective, run, results)
    O-->>R: final briefing
    R->>Obs: PIPELINE_COMPLETED
    R-->>H: Run (COMPLETED/PARTIAL)
    H-->>API: Run
    API-->>Operator: ack / result
```

---

## 3. Workflow: a brain spawns a sub-agent

```mermaid
sequenceDiagram
    participant A as Brain A (parent)
    participant Reg as Registry
    participant Bus as MessageBus
    participant B as Brain B (sub-agent)
    participant Obs as Observer

    A->>A: spawn_agent(capability, objective, ancestry…)
    A->>Obs: AGENT_SPAWNED
    A->>Reg: find_by_capability(capability)
    alt no brain for capability
        Reg-->>A: None
        A-->>A: AgentCall(status=FAILED, error)
    else brain found
        Reg-->>A: BrainInfo(brain_id=B)
        A->>Bus: enqueue TASK → B (reply=agent:<call_id>)
        Bus->>B: dequeue TASK
        B->>B: AgentLoop runs, logs judgment
        B->>Bus: enqueue RESULT → agent:<call_id>
        Bus-->>A: dequeue RESULT (await, timeout)
        A->>Obs: AGENT_RETURNED
        A-->>A: AgentCall(status=COMPLETED, result)
    end
```

A timeout or missing capability yields `status=FAILED`; the parent continues.

---

## 4. Workflow: dependency-ordered task waves

```
plan() → [T1, T2, T3(depends_on T1)]

wave 1: dispatch T1, T2 in parallel ──► collect 2 results
wave 2: T3 ready (T1 done); inject T1.summary into T3.inputs.upstream
        dispatch T3 ──► collect 1 result
synthesize([R1, R2, R3])
```

Unsatisfiable dependencies (cycles / missing deps) fail only the stragglers with
`error="dependency_not_satisfiable"`; the rest of the run still completes.

---

## 5. Intake wireframe (UI)

```
┌──────────────────────────────────────────────────────────┐
│                                                            │
│                     Drop an idea.                          │
│        The harness takes over. Orchestrator routes.        │
│                                                            │
│   ┌────────────────────────────────────────────────────┐ │
│   │  I want to build a trading AI that …                │ │
│   │                                                     │ │
│   │  [ ● voice ]                            [ Run → ]   │ │
│   └────────────────────────────────────────────────────┘ │
│                 ⌘/Ctrl + Enter to run                      │
└──────────────────────────────────────────────────────────┘
```

Pipeline view: a grid of breathing **brain orbs** (idle / thinking / executing /
error) above a run list and a per-run synthesis panel. See `frontend/README.md`.

---

## 6. HTTP API reference

Base URL defaults to `http://localhost:8000`. Defined in `harness/api/main.py`
and `intake/api.py`.

| Method | Path                  | Body / Query                              | Returns |
|--------|-----------------------|-------------------------------------------|---------|
| GET    | `/health`             | —                                         | `{status, environment, in_memory, anthropic}` |
| POST   | `/intake`             | `{text: str, wait: bool=false}`           | `IntakeResponse` |
| POST   | `/intake/voice`       | `{audio_base64: str, wait: bool=false}`   | `IntakeResponse` |
| GET    | `/pipelines`          | —                                         | `[{pipeline_id, idea, status}]` |
| GET    | `/pipelines/{id}`     | `id` = objective_id                        | `{pipeline_id, run_id?, idea, plan[], history[], output, status}` |
| GET    | `/brains`             | —                                         | `[BrainInfo]` (live state for orbs) |
| GET    | `/ledger`             | `?brain_id=&limit=`                        | `[JudgmentEntry]` |
| GET    | `/doctrine`           | `?limit=`                                 | `[JudgmentEntry]` (active) |
| GET    | `/observer/events`    | `?context_id=&limit=`                      | `[AuditEvent]` (context_id = run_id) |
| GET    | `/observer/stream`    | —                                         | SSE stream of `AuditEvent` |

### `IntakeResponse`

```json
{
  "pipeline_id": "<objective_id>",
  "status": "running | COMPLETED | PARTIAL | NEEDS_OPERATOR",
  "message": "Got it, running.",
  "idea": "<normalized statement>",
  "result": { "...Run.to_dict() when wait=true, else null" }
}
```

### Async vs. sync intake

- `wait=false` (default): returns immediately with `status="running"` and a
  `pipeline_id`. Poll `GET /pipelines/{pipeline_id}` for progress, or subscribe
  to `GET /observer/stream`.
- `wait=true`: blocks until the run completes and returns the full `Run` in
  `result`.
