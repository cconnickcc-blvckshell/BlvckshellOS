# Brain SDK — building a new brain

A brain is a self-contained specialist. The harness handles transport,
discovery, memory, and audit; a brain only declares what it does and how it
thinks.

## The fast path: extend `LLMBrain`

Most brains only need an identity, a capability list, and a system prompt.

```python
from brains._base.brain import LLMBrain


class ResearchBrain(LLMBrain):
    brain_id = "research"
    name = "Research Brain"
    description = "Gathers and synthesizes external research on a topic"
    capabilities = ["research", "literature_review"]
    system_prompt = (
        "You are the Research Brain. Given a topic, produce a tight, sourced "
        "briefing: key findings, the strongest counter-evidence, and what is "
        "still unknown. End with the single most decision-relevant insight."
    )
```

`LLMBrain` implements the full contract for you: it loads context from shared
memory (`get_context`), runs the think/act/observe loop, logs a Judgment Ledger
entry (`log_judgment`), and emits a `Result` over the bus.

## Adding tools

A tool is a small, explicit capability the model can call mid-loop.

```python
from brains._base.tools import FunctionTool


async def _score(args: dict) -> dict:
    return {"score": sum(args["values"]) / len(args["values"])}


class ResearchBrain(LLMBrain):
    ...
    tools = [
        FunctionTool(
            name="score",
            description="Average a list of numeric values.",
            input_schema={
                "type": "object",
                "properties": {"values": {"type": "array", "items": {"type": "number"}}},
                "required": ["values"],
            },
            func=_score,
        )
    ]
```

You can also subclass `BaseTool` directly and implement `async def run(self, arguments)`.

## The full contract: extend `BaseBrain`

For non-LLM or custom brains, extend `BaseBrain` and implement:

- `async def handle_task(self, task: HarnessMessage) -> HarnessMessage`
- `async def get_context(self, context_id: str) -> BrainContext`
- `async def log_judgment(self, entry: JudgmentEntry) -> None`

Do **not** override `register`, `heartbeat`, or `serve` — the harness owns the
lifecycle.

## Registering the brain

Brains are declared in **configuration**, never in harness code.

**In-process (default):** add the `module:ClassName` to
`BLVCKSHELL_WORKER_BRAIN_MODULES` (in `.env` or `Settings`):

```bash
BLVCKSHELL_WORKER_BRAIN_MODULES="brains.examples.venture:VentureBrain,brains.research.brain:ResearchBrain"
```

`harness/core/brain_loader.py` imports each entry at startup. A bad entry is
logged and skipped — it never stops the harness.

**Distributed:** add the class to the `BRAINS` map in `scripts/run_brain.py`,
set `BLVCKSHELL_RUN_WORKERS_IN_PROCESS=false` on the harness, and run the brain
in its own container:

```bash
BRAIN_ID=research python -m scripts.run_brain research
```

That's it. The Orchestrator discovers the new capabilities through the registry
and routes to them automatically — it never routes to a capability that is not
registered.

## Spawning sub-agents

Any brain can spawn a child agent for a capability, await its result, and use it.
`spawn_agent` is on `BaseBrain`, so every brain has it. The ancestry ids come
from the incoming task message's `metadata`.

```python
async def handle_task(self, task):  # inside a brain
    sub = await self.spawn_agent(
        capability="market_analysis",
        objective="Analyse options IV rank for SPY over the last 30 days",
        inputs={"ticker": "SPY", "window_days": 30},
        parent_task_id=task.payload["id"],
        run_id=task.metadata["run_id"],
        objective_id=task.metadata["objective_id"],
        timeout=60.0,
    )
    if sub.status == TaskStatus.COMPLETED:
        iv_analysis = sub.result
    else:
        iv_analysis = "Market analysis unavailable."  # sub.error has detail
    ...
```

The sub-agent is dispatched over the bus to whatever brain is registered for the
capability and runs through the full machinery (agent loop, judgment logging).
A failed spawn returns an `AgentCall` with `status=FAILED` and `error` set — it
never raises, so it cannot crash the parent brain or the harness. The Observer
records `AGENT_SPAWNED` and `AGENT_RETURNED`.

## Logging judgments well

Every meaningful decision should become a `JudgmentEntry`: state the `belief`, a
calibrated `confidence` (0–1), the `evidence` and `assumptions` behind it. Once
the real outcome is known, call `ledger.record_outcome(...)`; correct,
high-confidence beliefs become candidates for doctrine.
