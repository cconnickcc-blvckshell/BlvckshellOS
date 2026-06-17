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

**In-process (default):** add the class to `DEFAULT_WORKER_BRAINS` in
`harness/core/harness.py`.

**Distributed:** add the class to the `BRAINS` map in `scripts/run_brain.py`,
set `BLVCKSHELL_RUN_WORKERS_IN_PROCESS=false` on the harness, and run the brain
in its own container:

```bash
BRAIN_ID=research python -m scripts.run_brain research
```

That's it. CKOS will discover the new capabilities through the registry and route
to them automatically — it never routes to a capability that is not registered.

## Logging judgments well

Every meaningful decision should become a `JudgmentEntry`: state the `belief`, a
calibrated `confidence` (0–1), the `evidence` and `assumptions` behind it. Once
the real outcome is known, call `ledger.record_outcome(...)`; correct,
high-confidence beliefs become candidates for doctrine.
