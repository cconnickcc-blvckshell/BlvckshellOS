# Brain SDK — building a new brain

A brain is a specialist. The harness makes brains plug-and-play: it handles
registration, message delivery, heartbeats, the agent loop, and auditing. You
write the specialization.

## The contract

Every brain extends `BaseBrain` (`brains/_base/brain.py`) and implements three
methods:

```python
class BaseBrain(ABC):
    brain_id: str
    name: str
    description: str
    capabilities: list[str]
    model: str
    tools: list[BaseTool]

    async def handle_task(self, task: HarnessMessage) -> HarnessMessage: ...
    async def get_context(self, context_id: str) -> BrainContext: ...
    async def log_judgment(self, entry: JudgmentEntry) -> None: ...

    async def register(self) -> None: ...   # provided — do not override
    async def heartbeat(self) -> None: ...   # provided — do not override
```

## The fast path: `LLMWorkerBrain`

Most brains follow the same shape (receive → context → think → judge → result).
`LLMWorkerBrain` (`brains/_base/worker.py`) implements all three abstract methods
for you. A new worker brain is just metadata:

```python
from harness.schemas.task import TaskPayload
from brains._base.worker import LLMWorkerBrain


class ResearchBrain(LLMWorkerBrain):
    brain_id = "research"
    name = "Research Brain"
    description = "Gathers and synthesizes evidence for a question."
    capabilities = ["research", "synthesize_sources"]
    model = "stub-1"  # or claude-3-5-sonnet-latest, qwen2.5:14b, ...
    default_confidence = 0.6

    def system_prompt(self) -> str:
        return "Research Brain. Find evidence, cite it, synthesize a position."

    def belief_for(self, task: TaskPayload, loop_content: str) -> str:
        return f"Researched: {task.objective[:160]}"
```

Then register it in `brains/catalog.py` and add it to `default_brains` in
`harness/bootstrap.py`. That's it — CKOS can now route to `research` /
`synthesize_sources`, in-process or as its own container.

## Tools

Tools are the brain's hands. Extend `BaseTool` (`brains/_base/tools.py`):

```python
from typing import Any
from brains._base.tools import BaseTool, ToolResult


class FetchUrlTool(BaseTool):
    name = "fetch_url"
    description = "Fetch the text content of a URL."
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"url": {"type": "string"}},
        "required": ["url"],
    }

    async def run(self, **kwargs: Any) -> ToolResult:
        ...
        return ToolResult(ok=True, output={"text": "..."})
```

Pass tools when constructing the brain: `ResearchBrain(runtime, tools=[FetchUrlTool()])`.
The agent loop advertises each tool's schema to the model and executes requested
calls, feeding results back as observations — with every call audited.

## The Judgment Ledger (LOCKED v1)

Every meaningful decision is recorded with its evidence and confidence:

```python
JudgmentEntry(
    id: str
    brain_id: str
    context_id: str
    timestamp: datetime
    belief: str                 # what the brain believes/decided
    confidence: float           # 0.0 - 1.0
    evidence: list[str]
    assumptions: list[str]
    contradicts: list[str]      # ids of beliefs this contradicts
    outcome: str | None         # filled in when the result is known
    outcome_timestamp: datetime | None
    was_correct: bool | None
    doctrine_promoted: bool     # promoted into validated doctrine
    retired: bool               # superseded
    changelog: list[dict]       # full history of changes
)
```

`LLMWorkerBrain` logs one automatically per task. Validated, high-confidence
beliefs can be promoted to the append-only doctrine store via
`SharedMemory.promote_doctrine(entry_id)`.

## Running a brain standalone

```bash
poetry run python -m scripts.register_brain research   # connect to the bus and serve
poetry run python -m scripts.register_brain --list     # list available brains
```

Or one brain per container with `docker/Dockerfile.brain` (see
`docker/docker-compose.yml`, profile `distributed`).
