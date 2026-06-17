"""Tests for the memory tiers: context store, ledger, doctrine, episodic."""

from __future__ import annotations

from harness.core.persistence import InMemoryTable
from harness.schemas.judgment import JudgmentEntry
from memory.context_store import InMemoryContextStore
from memory.doctrine_store import DoctrineStore
from memory.episodic_store import EpisodicStore
from memory.judgment_ledger import JudgmentLedger


async def test_context_store_set_get_delete() -> None:
    store = InMemoryContextStore(ttl_seconds=100)
    await store.set("ctx", "objective", "build a thing")
    assert await store.get("ctx", "objective") == "build a thing"
    assert await store.get_all("ctx") == {"objective": "build a thing"}
    await store.delete("ctx")
    assert await store.get_all("ctx") == {}


async def test_context_store_expiry() -> None:
    store = InMemoryContextStore(ttl_seconds=0)
    await store.set("ctx", "k", "v")
    # TTL of 0 means the entry is immediately considered expired on next access.
    assert await store.get("ctx", "k") is None


async def test_judgment_ledger_record_and_query() -> None:
    ledger = JudgmentLedger(table=InMemoryTable("ledger"))
    entry = JudgmentEntry(brain_id="venture", context_id="c1", belief="feasible", confidence=0.8)
    await ledger.record(entry)
    assert (await ledger.get(entry.id)).belief == "feasible"
    assert len(await ledger.for_context("c1")) == 1
    assert len(await ledger.for_brain("venture")) == 1


async def test_judgment_outcome_and_promotion() -> None:
    ledger = JudgmentLedger(table=InMemoryTable("ledger"))
    doctrine = DoctrineStore(table=InMemoryTable("doctrine"))
    entry = JudgmentEntry(brain_id="venture", context_id="c1", belief="feasible", confidence=0.9)
    await ledger.record(entry)

    updated = await ledger.record_outcome(entry.id, outcome="shipped", was_correct=True)
    assert updated.was_correct is True
    assert updated.outcome == "shipped"

    promoted = await ledger.promote_to_doctrine(entry.id, doctrine)
    assert promoted.doctrine_promoted is True
    assert len(await doctrine.active()) == 1


async def test_doctrine_supersede() -> None:
    doctrine = DoctrineStore(table=InMemoryTable("doctrine"))
    e1 = JudgmentEntry(brain_id="b", context_id="c", belief="old", confidence=0.7)
    e2 = JudgmentEntry(brain_id="b", context_id="c", belief="new", confidence=0.9)
    await doctrine.append(e1)
    await doctrine.append(e2)
    await doctrine.supersede(e1.id, e2.id)
    active = await doctrine.active()
    assert {row["belief"] for row in active} == {"new"}


async def test_episodic_recent_ordering() -> None:
    store = EpisodicStore(table=InMemoryTable("episodic"))
    await store.record_run(context_id="a", objective="o1", result={"x": 1})
    await store.record_run(context_id="b", objective="o2", result={"x": 2})
    recent = await store.recent(limit=10)
    assert len(recent) == 2
