"""Tests for the shared-memory tiers and doctrine promotion."""

from __future__ import annotations

from memory.context_store import InMemoryContextStore
from memory.conversation_store import InMemoryConversationStore
from memory.doctrine_store import InMemoryDoctrineStore
from memory.judgment_ledger import InMemoryJudgmentLedger
from memory.notes_store import InMemoryNotesStore
from memory.opinions_store import InMemoryOpinionsStore

from harness.core.embeddings import HashEmbeddingClient
from harness.core.memory import SharedMemory
from harness.schemas.judgment import JudgmentEntry, OutcomeRecord


def _memory() -> SharedMemory:
    return SharedMemory(
        context_store=InMemoryContextStore(),
        ledger=InMemoryJudgmentLedger(),
        doctrine=InMemoryDoctrineStore(),
        conversations=InMemoryConversationStore(),
        notes=InMemoryNotesStore(),
        opinions=InMemoryOpinionsStore(),
        embeddings=HashEmbeddingClient(),
    )


async def test_working_memory_set_get_append() -> None:
    mem = _memory()
    await mem.connect()
    await mem.remember("c1", "k", {"a": 1})
    assert await mem.recall("c1", "k") == {"a": 1}
    await mem.append_working("c1", "history", "first")
    await mem.append_working("c1", "history", "second")
    assert await mem.recall("c1", "history") == ["first", "second"]


async def test_record_and_list_judgments_for_context() -> None:
    mem = _memory()
    await mem.connect()
    await mem.record_judgment(
        JudgmentEntry(brain_id="venture", context_id="c1", belief="b1", confidence=0.9)
    )
    await mem.record_judgment(
        JudgmentEntry(brain_id="venture", context_id="c2", belief="b2", confidence=0.9)
    )
    ctx1 = await mem.ledger.list_for_context("c1")
    assert len(ctx1) == 1
    assert ctx1[0].belief == "b1"


async def test_doctrine_promotion_requires_correct_and_confident() -> None:
    mem = _memory()
    await mem.connect()
    entry = await mem.record_judgment(
        JudgmentEntry(brain_id="venture", context_id="c1", belief="high", confidence=0.9)
    )
    # Not yet correct -> not promotable.
    assert await mem.promote_to_doctrine(entry.id) is None

    await mem.ledger.record_outcome(
        entry.id, OutcomeRecord(actual_outcome="worked", outcome_quality=0.9)
    )
    promoted = await mem.promote_to_doctrine(entry.id)
    assert promoted is not None
    assert promoted.doctrine_promoted is True

    active = await mem.doctrine.list_active()
    assert any(d.id == entry.id for d in active)


async def test_doctrine_promotion_rejects_low_confidence() -> None:
    mem = _memory()
    await mem.connect()
    entry = await mem.record_judgment(
        JudgmentEntry(brain_id="venture", context_id="c1", belief="low", confidence=0.5)
    )
    await mem.ledger.record_outcome(
        entry.id, OutcomeRecord(actual_outcome="worked", outcome_quality=0.9)
    )
    assert await mem.promote_to_doctrine(entry.id) is None


async def test_load_context_assembles_tiers() -> None:
    mem = _memory()
    await mem.connect()
    await mem.remember("c1", "idea", "build a thing")
    await mem.record_judgment(
        JudgmentEntry(brain_id="venture", context_id="c1", belief="b1", confidence=0.8)
    )
    ctx = await mem.load_context("c1", "venture")
    assert ctx.context_id == "c1"
    assert ctx.working_memory["idea"] == "build a thing"
    assert len(ctx.recent_judgments) == 1
