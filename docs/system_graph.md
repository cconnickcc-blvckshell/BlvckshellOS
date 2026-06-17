# System Graph

A full graph of the Blvckshell harness: module structure, runtime objects, data
stores, and the schema hierarchy. Mermaid renders on GitHub.

---

## 1. Module dependency graph

```mermaid
graph LR
    subgraph schemas["harness/schemas (leaf contracts)"]
        msg[message]
        task[task]
        result[result]
        judgment[judgment]
        objective[objective]
        braininfo[brain_info]
        audit[audit]
    end

    subgraph services["harness/core (services)"]
        llm[llm]
        bus[message_bus]
        registry[registry]
        observer[observer]
        memory[memory]
    end

    subgraph engine["harness/core (engine)"]
        agentloop[agent_loop]
        orch[orchestrator]
        router[router]
        loader[brain_loader]
        harness[harness]
    end

    subgraph brains["brains"]
        base[_base/brain]
        tools[_base/tools]
        venture[examples/venture]
        commander[examples/commander]
        capital[examples/capital]
    end

    subgraph memstore["memory (backends)"]
        ctx[context_store]
        ledger[judgment_ledger]
        doctrine[doctrine_store]
    end

    subgraph edge["edges"]
        api[api/main]
        intake[intake/api]
    end

    objective --> task
    objective --> result
    braininfo --> judgment

    memory --> ctx & ledger & doctrine & observer
    agentloop --> llm & observer & tools
    orch --> llm & registry & memory & observer
    router --> bus & memory & observer & orch
    base --> bus & registry & memory & observer & llm & agentloop & tools
    loader --> base
    venture & commander & capital --> base
    harness --> loader & orch & router & bus & registry & memory & observer & llm & base
    api --> harness & intake
    intake --> harness
```

---

## 2. Runtime object graph (single process)

```mermaid
graph TB
    H[Harness]
    H --> RT[BrainRuntime]
    H --> ORCH[Orchestrator]
    H --> WK[workers: list_BaseBrain_]
    RT --> BUS[(MessageBus)]
    RT --> REG[(BrainRegistry)]
    RT --> MEM[SharedMemory]
    RT --> OBS[Observer]
    RT --> LLM[LLMClient]
    MEM --> CTX[(ContextStore)]
    MEM --> LED[(JudgmentLedger)]
    MEM --> DOC[(DoctrineStore)]
    WK --> B1[VentureBrain]
    WK --> B2[CommanderBrain]
    WK --> B3[CapitalBrain]
    B1 & B2 & B3 -.share.-> RT
    H -.per run.-> ROUTER[PipelineRouter]
    ROUTER --> ORCH
    ROUTER --> BUS
```

All workers share one `BrainRuntime`. The `Orchestrator` is owned by the harness
and is **not** in `workers` and **not** in the registry. A fresh `PipelineRouter`
is created per run.

---

## 3. Execution hierarchy (data)

```mermaid
graph TD
    O[Objective\nobjective_id, statement] --> R[Run\nrun_id, status, output]
    R --> T1[Task\ntask_id, capability, assigned_brain]
    R --> T2[Task]
    R --> Tn[Task ...]
    T1 --> AC1[AgentCall\nagent_call_id, spawned_by, result]
    T1 --> AC2[AgentCall ...]
    R --> RES[Result*\none per Task]
```

Ancestry travels on every `TASK` message in `metadata`
(`objective_id` → `run_id` → `task_id`), enabling correct `AgentCall` parentage.

---

## 4. Memory tiers & persistence

```mermaid
graph LR
    subgraph tier1["Tier 1 — Working memory"]
        CTX[ContextStore]
    end
    subgraph tier2["Tier 2 — Episodic"]
        LED[JudgmentLedger]
    end
    subgraph tier3["Tier 3 — Doctrine"]
        DOC[DoctrineStore]
    end
    CTX -->|Redis hash, TTL 24h| REDIS[(Redis)]
    LED -->|table judgment_ledger| SUPA[(Supabase)]
    DOC -->|table doctrine, append-only| SUPA
    LED -.promote correct + conf>=0.8.-> DOC
    AUD[Observer / AuditStore] -->|table audit_log| SUPA
```

With offline defaults, all four use in-memory backends — no Redis or Supabase.

---

## 5. Brain state machine (UI orbs)

```mermaid
stateDiagram-v2
    [*] --> IDLE: register()
    IDLE --> THINKING: task received
    THINKING --> EXECUTING: agent loop / tools
    EXECUTING --> IDLE: result emitted
    THINKING --> ERROR: exception
    EXECUTING --> ERROR: exception
    ERROR --> IDLE: next task
    IDLE --> OFFLINE: serve loop stops
    OFFLINE --> [*]
```

Colors: idle = dim purple, thinking = pulsing purple, executing = white pulse,
error = red, offline = grey. See `frontend/components/BrainOrb.tsx`.
