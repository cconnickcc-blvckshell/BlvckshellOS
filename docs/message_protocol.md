# Message Protocol

Every object that crosses the message bus is a `HarnessMessage`
(`harness/schemas/message.py`). No exceptions. Get this right and everything else
follows.

## `HarnessMessage`

| Field | Type | Notes |
|-------|------|-------|
| `id` | `str` | UUID, generated at creation. |
| `timestamp` | `datetime` | UTC, timezone-aware. |
| `source` | `str` | `brain_id`, `"intake"`, or `"harness"`. Non-empty. |
| `destination` | `str` | `brain_id`, `"harness"`, or `"broadcast"`. Non-empty. |
| `message_type` | `MessageType` | `TASK \| RESULT \| EVENT \| BROADCAST \| ACK`. |
| `priority` | `int` | 1–5, 5 is highest. Validated. |
| `payload` | `dict` | Task / result / event content. |
| `context_id` | `str` | Links every message in one pipeline run. |
| `parent_id` | `str \| None` | The message this responds to. |
| `metadata` | `dict` | Tracing, timing, model, tokens, cost. |

### Message types

- **TASK** — assigning work to a brain.
- **RESULT** — a brain returning completed work.
- **EVENT** — a brain broadcasting that something happened.
- **BROADCAST** — the harness announcing to all brains.
- **ACK** — acknowledgment of receipt.

### Replying

`HarnessMessage.reply(...)` builds a child message that inherits `context_id` and
sets `parent_id`, addressed back to the original `source`. This is how the
observer reconstructs a full pipeline trace.

```python
result = task.reply(
    source="venture",
    message_type=MessageType.RESULT,
    payload=result_payload.model_dump(mode="json"),
)
```

## Addressing & channels

Channels are addresses. Publishing to a `brain_id` delivers to that brain;
publishing to `broadcast` fans out to every subscriber. The harness correlates
returning results on the `harness` address; intake correlates final pipeline
results on the `intake` address, keyed by `context_id`.

## Payload schemas

- **`TaskPayload`** (`harness/schemas/task.py`) — `task_id`, `capability`,
  `objective`, `inputs`, `constraints`, `depends_on`, `status`, `assigned_brain`.
- **`ResultPayload`** (`harness/schemas/result.py`) — `task_id`, `brain_id`,
  `status`, `summary`, `output`, `artifacts`, `judgment_ids`, `error`, `usage`.
- **`JudgmentEntry`** (`harness/schemas/judgment.py`) — the **locked v1** ledger
  schema. See `docs/brain_sdk.md`.
- **`ObserverEvent`** (`harness/schemas/event.py`) — the audit-log record.

## Example: a TASK envelope

```json
{
  "id": "f1d2...",
  "timestamp": "2026-06-17T10:00:00+00:00",
  "source": "harness",
  "destination": "venture",
  "message_type": "TASK",
  "priority": 4,
  "payload": {
    "task_id": "task-1-validate_idea",
    "capability": "validate_idea",
    "objective": "Validate: build a trading AI that outperforms the market",
    "depends_on": []
  },
  "context_id": "run-abc",
  "parent_id": null,
  "metadata": {"capability": "validate_idea"}
}
```
