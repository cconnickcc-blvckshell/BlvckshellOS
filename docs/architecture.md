# Blvckshell Harness — Architecture

The harness is the nervous system of an autonomous organization. Every brain is a
specialist; the harness is what makes them one. It is an **execution engine**, not
a chatbot.

## The six layers

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

| Layer | Module | Responsibility |
|-------|--------|----------------|
| Intake | `intake/` | Capture an idea (text, voice, API) and hand a normalized objective to CKOS. |
| CKOS Router | `brains/ckos/`, `harness/core/router.py` | Understand intent, decompose into tasks, route to brains, aggregate results. |
| Message Bus | `harness/core/message_bus.py` | Pub/sub transport for every `HarnessMessage`. Redis or in-process. |
| Brain Registry | `harness/core/registry.py` | Track who is online and what they can do; health via heartbeats. |
| Shared Memory | `memory/`, `harness/core/memory.py` | Working (TTL) / episodic / doctrine memory + the Judgment Ledger. |
| Observer | `harness/core/observer.py` | Audit every event; live stream + persisted log. |

## The agent loop (per brain)

```
RECEIVE TASK → LOAD CONTEXT → THINK (LLM + tools) → ACT (tool calls)
   → OBSERVE (results) → ITERATE → EMIT RESULT → LOG TO JUDGMENT LEDGER
```

Implemented once in `harness/core/agent_loop.py` and reused by every brain via
`BaseBrain.think`. Each model call and tool call is audited by the observer.

## Pluggable backends (zero-dependency by default)

Every external system has an in-process fallback, so the whole stack boots and the
end-to-end pipeline passes with no Redis, Supabase, or API keys.

| Concern | Default (offline) | Production |
|---------|-------------------|------------|
| Message bus | `InMemoryMessageBus` | `RedisMessageBus` (`BLVCKSHELL_REDIS_URL`) |
| Working memory | `InMemoryContextStore` | `RedisContextStore` |
| Episodic / doctrine / ledger / events | `InMemoryTable` | `SupabaseTable` (`BLVCKSHELL_SUPABASE_URL/KEY`) |
| Inference | `StubLLMClient` (deterministic) | `AnthropicLLMClient` / `OllamaLLMClient` |

Selection is centralized in `harness/config.py` and the per-component factories
(`create_message_bus`, `create_context_store`, `create_table`, `create_llm_client`).

## Shared memory tiers

```
WORKING MEMORY (Redis, TTL 24h)     → active pipeline context, in-flight outputs
EPISODIC MEMORY (Supabase)          → completed runs, full Judgment Ledger, history
DOCTRINE STORE (Supabase, append)   → validated beliefs, never deleted, only superseded
```

## Topology

- **In-process (default):** the API runs the full brain federation in one process.
  `BLVCKSHELL_INPROCESS_BRAINS=true`.
- **Distributed:** each brain runs in its own container (`docker/Dockerfile.brain`,
  `scripts/register_brain.py`) communicating over the Redis bus. Set
  `BLVCKSHELL_INPROCESS_BRAINS=false` for the API.

## Failure isolation

A brain failing must never crash the harness. Handler exceptions on the bus are
caught and logged; a brain that throws while handling a task returns a `FAILED`
result and emits a `task_failed` event instead of propagating.
