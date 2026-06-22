"""Tests for judgment outcome capture and the learning loop."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from harness.config import get_settings
from harness.core.embeddings import HashEmbeddingClient
from harness.core.memory import DOCTRINE_PROMOTION_THRESHOLD, SharedMemory
from harness.schemas.judgment import JudgmentEntry, OutcomeRecord
from memory.context_store import InMemoryContextStore
from memory.conversation_store import InMemoryConversationStore
from memory.doctrine_store import InMemoryDoctrineStore
from memory.judgment_ledger import InMemoryJudgmentLedger
from memory.notes_store import InMemoryNotesStore
from memory.opinions_store import InMemoryOpinionsStore


@pytest.fixture
def memory() -> SharedMemory:
    """Offline shared memory with in-memory backends."""
    return SharedMemory(
        context_store=InMemoryContextStore(),
        ledger=InMemoryJudgmentLedger(),
        doctrine=InMemoryDoctrineStore(),
        conversations=InMemoryConversationStore(),
        notes=InMemoryNotesStore(),
        opinions=InMemoryOpinionsStore(),
        embeddings=HashEmbeddingClient(),
    )


async def test_outcome_recording_updates_ledger(memory: SharedMemory) -> None:
    await memory.connect()
    entry = await memory.record_judgment(
        JudgmentEntry(
            brain_id="venture",
            context_id="run-1",
            belief="GO on trading AI",
            confidence=0.85,
        )
    )
    updated = await memory.record_outcome(
        entry.id,
        OutcomeRecord(actual_outcome="Launched MVP successfully", outcome_quality=0.9),
    )
    assert updated is not None
    assert updated.outcome == "Launched MVP successfully"
    assert updated.was_correct is True
    assert any(c["action"] == "outcome_recorded" for c in updated.changelog)


async def test_high_quality_outcome_promotes_doctrine(memory: SharedMemory) -> None:
    await memory.connect()
    entry = await memory.record_judgment(
        JudgmentEntry(
            brain_id="venture",
            context_id="run-1",
            belief="Market timing is favorable",
            confidence=DOCTRINE_PROMOTION_THRESHOLD,
        )
    )
    await memory.record_outcome(
        entry.id,
        OutcomeRecord(actual_outcome="Validated in market", outcome_quality=0.95),
    )
    refreshed = await memory.ledger.get(entry.id)
    assert refreshed is not None
    assert refreshed.doctrine_promoted is True
    doctrine = await memory.doctrine.list_active()
    assert any(d.belief == entry.belief for d in doctrine)


async def test_negative_outcome_reduces_doctrine_confidence(memory: SharedMemory) -> None:
    await memory.connect()
    promoted = JudgmentEntry(
        brain_id="venture",
        context_id="run-1",
        belief="Trading strategies outperform in volatile markets",
        confidence=0.9,
        doctrine_promoted=True,
    )
    await memory.doctrine.promote(promoted)

    judgment = await memory.record_judgment(
        JudgmentEntry(
            brain_id="venture",
            context_id="run-2",
            belief="Trading strategies need revision after volatile markets shift",
            confidence=0.7,
        )
    )
    await memory.record_outcome(
        judgment.id,
        OutcomeRecord(actual_outcome="Strategy failed in live trading", outcome_quality=-0.7),
    )

    doctrine = await memory.doctrine.list_active()
    target = next(d for d in doctrine if "volatile markets" in d.belief.lower())
    assert target.confidence < 0.9
    assert any(c["action"] == "confidence_reduced" for c in target.changelog)


async def test_belief_update_on_outcome(memory: SharedMemory) -> None:
    await memory.connect()
    entry = await memory.record_judgment(
        JudgmentEntry(
            brain_id="venture",
            context_id="run-1",
            belief="Product launch timing",
            confidence=0.75,
        )
    )
    updated = await memory.record_outcome(
        entry.id,
        OutcomeRecord(actual_outcome="Strong launch", outcome_quality=0.9),
    )
    assert updated is not None
    assert updated.confidence > 0.75
    assert any(c["action"] == "belief_updated" for c in updated.changelog)


async def test_list_by_belief_keyword(memory: SharedMemory) -> None:
    await memory.connect()
    await memory.record_judgment(
        JudgmentEntry(
            brain_id="venture", context_id="c1", belief="Alpha trading thesis", confidence=0.8
        )
    )
    await memory.record_judgment(
        JudgmentEntry(
            brain_id="capital", context_id="c2", belief="Beta allocation plan", confidence=0.8
        )
    )
    hits = await memory.ledger.list_by_belief_keyword("trading", limit=10)
    assert len(hits) == 1
    assert hits[0].belief.startswith("Alpha")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """API client with offline harness."""
    monkeypatch.setenv("BLVCKSHELL_USE_IN_MEMORY_BUS", "true")
    monkeypatch.setenv("BLVCKSHELL_USE_FAKE_LLM", "true")
    monkeypatch.setenv("BLVCKSHELL_LOG_LEVEL", "WARNING")
    get_settings.cache_clear()
    from harness.api.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_outcome_api_route_returns_200(client: TestClient) -> None:
    chat = client.post("/chat", json={"message": "Help me validate a trading AI idea"})
    assert chat.status_code == 200
    judgment_ids = chat.json().get("judgment_ids") or []
    assert judgment_ids

    resp = client.post(
        f"/judgments/{judgment_ids[0]}/outcome",
        json={"actual_outcome": "Pilot succeeded", "outcome_quality": 0.85},
    )
    assert resp.status_code == 200
    assert resp.json()["outcome"] == "Pilot succeeded"
