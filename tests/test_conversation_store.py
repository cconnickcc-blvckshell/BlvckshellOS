"""Tests for conversation persistence."""

from __future__ import annotations

import pytest
from memory.conversation_store import InMemoryConversationStore


@pytest.fixture
async def store() -> InMemoryConversationStore:
    """Connected in-memory conversation store."""
    instance = InMemoryConversationStore()
    await instance.connect()
    return instance


async def test_append_and_get_history(store: InMemoryConversationStore) -> None:
    session_id = await store.get_or_create_session("operator")
    await store.append(session_id, "operator", "Hello Blvckbot")
    await store.append(session_id, "blvckbot", "Hello operator", brain_id="blvckbot")
    history = await store.get_history(session_id)
    assert len(history) == 2
    assert history[0].role == "operator"
    assert history[1].role == "blvckbot"


async def test_search_history(store: InMemoryConversationStore) -> None:
    session_id = await store.get_or_create_session("operator")
    await store.append(session_id, "operator", "We are building a trading platform")
    hits = await store.search_history("trading", limit=5)
    assert len(hits) == 1
    assert hits[0].session_id == session_id


async def test_list_sessions(store: InMemoryConversationStore) -> None:
    session_id = await store.get_or_create_session("operator")
    await store.append(session_id, "operator", "First message")
    sessions = await store.list_sessions()
    assert any(s.session_id == session_id for s in sessions)
    assert sessions[0].message_count >= 1


async def test_history_persists_within_store_instance(store: InMemoryConversationStore) -> None:
    session_id = await store.get_or_create_session("operator")
    await store.append(session_id, "operator", "Persist me")
    await store.append(session_id, "blvckbot", "Acknowledged", brain_id="blvckbot")
    history = await store.get_history(session_id)
    assert len(history) == 2
