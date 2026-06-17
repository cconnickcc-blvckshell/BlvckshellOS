# Message Protocol

Every message flowing through the harness conforms to `HarnessMessage`
(`harness/schemas/message.py`). No exceptions. Get this right and everything else
follows.

## HarnessMessage

| Field          | Type             | Notes                                            |
|----------------|------------------|--------------------------------------------------|
| `id`           | `str` (UUID)     | Generated at creation.                            |
| `timestamp`    | `datetime` (UTC) | Generated at creation.                            |
| `source`       | `str`            | `brain_id`, `"intake"`, `"harness"`, or `pipeline:<id>`. |
| `destination`  | `str`            | `brain_id`, `"harness"`, or `"broadcast"`.        |
| `message_type` | `MessageType`    | `TASK | RESULT | EVENT | BROADCAST | ACK`.         |
| `priority`     | `int` (1–5)      | 5 is highest. Defaults to 3.                       |
| `payload`      | `dict`           | Task/result/event content.                        |
| `context_id`   | `str`            | Links all messages in one pipeline run.           |
| `parent_id`    | `str | None`     | The message this responds to.                     |
| `metadata`     | `dict`           | Tracing, timing, model, tokens, cost.             |

### Message types

- **TASK** — the harness assigning work to a brain.
- **RESULT** — a brain returning completed work.
- **EVENT** — a brain broadcasting that something happened.
- **BROADCAST** — the harness announcing to all brains.
- **ACK** — acknowledgment of receipt.

### Helpers

- `message.reply(...)` builds a response that preserves `context_id` and links
  `parent_id` automatically.
- `message.to_wire()` / `HarnessMessage.from_wire(raw)` serialize to/from JSON
  for transport over the bus.

## Payload schemas

`TASK` payloads carry a `Task` (`harness/schemas/task.py`); `RESULT` payloads
carry a `Result` (`harness/schemas/result.py`).

### Task

`id`, `capability`, `objective`, `inputs`, `depends_on`, `priority`, `status`,
`assigned_brain`.

### Result

`task_id`, `brain_id`, `status` (`SUCCESS | FAILURE | NEEDS_OPERATOR`), `output`,
`summary`, `error`, `judgment_ids`, `metrics`.

## Bus addressing conventions

- A brain consumes the queue named by its `brain_id`.
- A pipeline run collects results on the reply address `pipeline:<context_id>`,
  so concurrent pipelines never cross wires.
- The Observer firehose channel mirrors every routed message for live viewing.
