"""Tests for Blvckbot conversational coordinator."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from harness.config import Settings, get_settings
from harness.core.harness import Harness
from harness.schemas.audit import AuditEventType
from judgment.outcome import JudgmentOutcome


@pytest.fixture
async def harness_with_blvckbot():
    """Harness with Blvckbot and specialists loaded."""
    settings = Settings(
        environment="test",
        use_in_memory_bus=True,
        use_fake_llm=True,
        log_level="WARNING",
        worker_brain_modules=(
            "brains.blvckbot.brain:BlvckbotBrain,"
            "brains.examples.venture:VentureBrain,"
            "brains.examples.commander:CommanderBrain,"
            "brains.examples.capital:CapitalBrain"
        ),
    )
    instance = Harness(settings)
    await instance.startup()
    try:
        yield instance
    finally:
        await instance.shutdown()


async def test_blvckbot_registered(harness_with_blvckbot: Harness) -> None:
    brains = await harness_with_blvckbot.registry.list_all()
    assert any(b.brain_id == "blvckbot" for b in brains)


async def test_run_chat_returns_response(harness_with_blvckbot: Harness) -> None:
    result = await harness_with_blvckbot.run_chat(
        "Help me build a trading AI that beats the market"
    )
    assert result["session_id"]
    assert result["response"]
    assert result["judgment_outcome"] in {o.value for o in JudgmentOutcome}


async def test_run_chat_delegates_to_specialists(harness_with_blvckbot: Harness) -> None:
    result = await harness_with_blvckbot.run_chat(
        "Validate my startup idea for an AI trading product"
    )
    assert isinstance(result["actions_taken"], list)
    assert len(result["actions_taken"]) >= 1


async def test_run_chat_records_judgment(harness_with_blvckbot: Harness) -> None:
    result = await harness_with_blvckbot.run_chat("What should I do about capital allocation?")
    assert result["judgment_ids"]
    entry = await harness_with_blvckbot.memory.ledger.get(result["judgment_ids"][0])
    assert entry is not None
    assert entry.brain_id == "blvckbot"


async def test_run_chat_persists_conversation(harness_with_blvckbot: Harness) -> None:
    first = await harness_with_blvckbot.run_chat("Remember this codename: Nightingale")
    await harness_with_blvckbot.run_chat(
        "What codename did I mention?",
        session_id=first["session_id"],
    )
    history = await harness_with_blvckbot.memory.conversations.get_history(first["session_id"])
    roles = [entry.role for entry in history]
    assert roles.count("operator") == 2
    assert roles.count("blvckbot") == 2


async def test_chat_emits_judgment_stage_events(harness_with_blvckbot: Harness) -> None:
    result = await harness_with_blvckbot.run_chat("Give me a quick plan for launch")
    events = await harness_with_blvckbot.observer.list_recent(
        context_id=f"chat-{result['session_id']}",
        limit=100,
    )
    types = {event.event_type for event in events}
    assert AuditEventType.JUDGMENT_STAGE_COMPLETED in types


@pytest.fixture
def chat_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("BLVCKSHELL_USE_IN_MEMORY_BUS", "true")
    monkeypatch.setenv("BLVCKSHELL_USE_FAKE_LLM", "true")
    monkeypatch.setenv("BLVCKSHELL_LOG_LEVEL", "WARNING")
    get_settings.cache_clear()
    from harness.api.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_chat_api_endpoint(chat_client: TestClient) -> None:
    resp = chat_client.post("/chat", json={"message": "Help me plan a product launch"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["response"]
    assert body["session_id"]


def test_chat_history_endpoint(chat_client: TestClient) -> None:
    created = chat_client.post("/chat", json={"message": "Track this thread please"})
    session_id = created.json()["session_id"]
    history = chat_client.get(f"/chat/history/{session_id}")
    assert history.status_code == 200
    assert len(history.json()) >= 2


def test_chat_sessions_endpoint(chat_client: TestClient) -> None:
    chat_client.post("/chat", json={"message": "Session listing test"})
    sessions = chat_client.get("/chat/sessions")
    assert sessions.status_code == 200
    assert len(sessions.json()) >= 1
