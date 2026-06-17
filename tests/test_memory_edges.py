"""Edge-case tests for memory and persistence backends."""

from __future__ import annotations

import pytest
from harness.core.persistence import InMemoryTable
from memory.context_store import InMemoryContextStore
from memory.doctrine_store import DoctrineStore
from memory.judgment_ledger import JudgmentLedger


async def test_persistence_requires_id() -> None:
    table = InMemoryTable("t")
    with pytest.raises(ValueError):
        await table.upsert({"no": "id"})


async def test_persistence_query_and_get_missing() -> None:
    table = InMemoryTable("t")
    await table.upsert({"id": "1", "kind": "a"})
    await table.upsert({"id": "2", "kind": "b"})
    assert len(await table.query(kind="a")) == 1
    assert await table.get("missing") is None
    assert len(await table.all()) == 2


async def test_ledger_outcome_and_promote_missing_returns_none() -> None:
    ledger = JudgmentLedger(table=InMemoryTable("l"))
    doctrine = DoctrineStore(table=InMemoryTable("d"))
    assert await ledger.record_outcome("nope", outcome="x", was_correct=True) is None
    assert await ledger.promote_to_doctrine("nope", doctrine) is None
    assert await ledger.retire("nope") is None


async def test_ledger_retire_marks_entry() -> None:
    from harness.schemas.judgment import JudgmentEntry

    ledger = JudgmentLedger(table=InMemoryTable("l"))
    entry = JudgmentEntry(brain_id="b", context_id="c", belief="x", confidence=0.5)
    await ledger.record(entry)
    retired = await ledger.retire(entry.id)
    assert retired.retired is True


async def test_context_store_get_missing_field() -> None:
    store = InMemoryContextStore(ttl_seconds=100)
    assert await store.get("ctx", "missing") is None
