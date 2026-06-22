"""The Reflection Job — how the system updates its point of view.

After a conversation, this reads the recent transcript plus the opinions
already held, and asks the LLM to (a) write a durable note summarizing what
was learned and (b) form new opinions or explicitly revise existing ones.
This is the mechanism by which the system's "point of view" changes over
time: it is retrieval and prompt injection, not literal persistent cognition,
but it is the same architecture used by any serious long-term agent, and it
produces real, inspectable, revisable output with provenance back to source
conversations.
"""

from __future__ import annotations

import json
import re

from harness.core.llm import LLMClient
from harness.core.memory import SharedMemory
from harness.logging_config import get_logger

logger = get_logger("reflection")

MIN_ENTRIES_TO_REFLECT = 2
TRANSCRIPT_LIMIT = 30

REFLECTION_SYSTEM_PROMPT = (
    "You are Blvckbot's reflection process. You just finished a conversation "
    "with the operator. Your job is to update durable personal memory: write "
    "a note summarizing what mattered, and form or revise standing opinions — "
    "real positions with reasoning, not database rows. An opinion should read "
    "like something a thoughtful collaborator would actually believe about "
    "the operator, the project, or the work, and should be revised (not "
    "just added) when new conversation contradicts or refines a prior one.\n\n"
    "Respond with ONLY a JSON object of this exact shape, no prose, no "
    "markdown fences:\n"
    "{\n"
    '  "note": "<2-5 sentence summary of this conversation>",\n'
    '  "topics": ["<short topic tag>", ...],\n'
    '  "opinions": [\n'
    "    {\n"
    '      "topic": "<short label>",\n'
    '      "statement": "<the position, stated plainly>",\n'
    '      "reasoning": "<why you hold it>",\n'
    '      "confidence": <0.0-1.0>,\n'
    '      "revises": "<id of an existing opinion this replaces, or null>"\n'
    "    }\n"
    "  ]\n"
    "}\n"
    "If nothing in this conversation rises to the level of a durable opinion, "
    'return an empty "opinions" list. Do not fabricate opinions just to fill '
    "the list."
)

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> dict | None:
    """Best-effort extraction of a JSON object from a model response."""
    match = _JSON_BLOCK_RE.search(text)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        logger.warning("reflection_json_parse_failed", snippet=text[:200])
        return None


async def run_reflection(
    memory: SharedMemory,
    llm: LLMClient,
    session_id: str,
    *,
    operator_id: str | None = None,
    model: str | None = None,
) -> None:
    """Run one reflection pass over a session's recent history.

    Writes a new :class:`~harness.schemas.memory.MemoryNote` and any new or
    revised :class:`~harness.schemas.memory.Opinion` entries. Failures are
    logged and swallowed — reflection is best-effort background work and must
    never affect the live conversation.
    """
    try:
        history = await memory.conversations.get_history(session_id, limit=TRANSCRIPT_LIMIT)
        if len(history) < MIN_ENTRIES_TO_REFLECT:
            return

        transcript = "\n".join(f"{e.role.upper()}: {e.content[:500]}" for e in history)
        existing = await memory.recall_opinions(transcript, operator_id=operator_id, limit=8)
        existing_block = (
            "\n".join(f"- [{o.id}] ({o.topic}) {o.statement}" for o in existing) or "(none yet)"
        )

        user_prompt = (
            f"CONVERSATION TRANSCRIPT:\n{transcript}\n\n"
            f"EXISTING STANDING OPINIONS:\n{existing_block}\n\n"
            "Write the note and any new/revised opinions now."
        )

        response = await llm.complete(
            system=REFLECTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            model=model,
            max_tokens=1024,
        )
        parsed = _extract_json(response.text)
        if parsed is None:
            logger.warning("reflection_no_parseable_output", session_id=session_id)
            return

        note_text = parsed.get("note")
        if isinstance(note_text, str) and note_text.strip():
            note = await memory.add_note(
                session_id,
                note_text.strip(),
                operator_id=operator_id,
                topics=[t for t in parsed.get("topics", []) if isinstance(t, str)],
                source_entry_ids=[e.id for e in history],
            )
            source_note_ids = [note.id]
        else:
            source_note_ids = []

        existing_ids = {o.id for o in existing}
        for raw in parsed.get("opinions", []):
            if not isinstance(raw, dict):
                continue
            topic = str(raw.get("topic", "")).strip()
            statement = str(raw.get("statement", "")).strip()
            reasoning = str(raw.get("reasoning", "")).strip()
            confidence = raw.get("confidence")
            if not topic or not statement or not isinstance(confidence, int | float):
                continue
            confidence = max(0.0, min(1.0, float(confidence)))
            revises = raw.get("revises")

            if isinstance(revises, str) and revises in existing_ids:
                await memory.revise_opinion(
                    revises,
                    statement,
                    reasoning,
                    confidence=confidence,
                    source_note_ids=source_note_ids,
                )
            else:
                await memory.add_opinion(
                    topic,
                    statement,
                    reasoning,
                    confidence=confidence,
                    operator_id=operator_id,
                    source_note_ids=source_note_ids,
                )

        logger.info("reflection_completed", session_id=session_id)
    except Exception as exc:  # reflection must never crash the harness
        logger.warning("reflection_failed", session_id=session_id, error=str(exc))
