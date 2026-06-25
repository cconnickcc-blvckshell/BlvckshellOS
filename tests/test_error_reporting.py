"""Tests for centralized error handling and structured API error responses."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from harness.config import get_settings
from harness.core.errors import HarnessError, format_exception, report_error
from harness.core.harness import Harness
from harness.schemas.audit import AuditEventType


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("BLVCKSHELL_USE_IN_MEMORY_BUS", "true")
    monkeypatch.setenv("BLVCKSHELL_USE_FAKE_LLM", "true")
    monkeypatch.setenv("BLVCKSHELL_LOG_LEVEL", "WARNING")
    get_settings.cache_clear()

    from harness.api.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_format_exception_never_blank() -> None:
    assert format_exception(Exception()) == "Exception: Unknown error"
    assert format_exception(Exception("boom")) == "boom"
    assert format_exception(None, fallback="fallback") == "fallback"


def test_harness_error_to_dict_includes_detail() -> None:
    err = HarnessError(
        "Chat failed",
        code="CHAT_FAILED",
        cause=RuntimeError("underlying"),
        context_id="chat-1",
    )
    body = err.to_dict(correlation_id="corr-123")
    assert body["code"] == "CHAT_FAILED"
    assert body["message"] == "Chat failed"
    assert "underlying" in body["detail"]
    assert body["correlation_id"] == "corr-123"


def test_api_returns_structured_404(client: TestClient) -> None:
    resp = client.get("/pipelines/does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == "HTTP_404"
    assert "does-not-exist" in body["detail"]
    assert body.get("correlation_id")


def test_api_returns_structured_validation_error(client: TestClient) -> None:
    resp = client.post("/intake", json={"text": "", "wait": False})
    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["detail"]


def test_chat_missing_brain_returns_structured_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLVCKSHELL_USE_IN_MEMORY_BUS", "true")
    monkeypatch.setenv("BLVCKSHELL_USE_FAKE_LLM", "true")
    monkeypatch.setenv("BLVCKSHELL_WORKER_BRAIN_MODULES", "brains.examples.venture:VentureBrain")
    monkeypatch.setenv("BLVCKSHELL_LOG_LEVEL", "WARNING")
    get_settings.cache_clear()

    from harness.api.main import create_app

    with TestClient(create_app()) as test_client:
        resp = test_client.post("/chat", json={"message": "hello"})
        assert resp.status_code == 503
        body = resp.json()
        assert body["code"] == "BRAIN_NOT_LOADED"
        assert "Blvckbot" in body["detail"]

    get_settings.cache_clear()


async def test_report_error_emits_observer_event() -> None:
    harness = Harness(
        settings=get_settings().model_copy(
            update={
                "use_in_memory_bus": True,
                "use_fake_llm": True,
                "worker_brain_modules": "",
                "log_level": "WARNING",
            }
        )
    )
    await harness.startup()
    try:
        await report_error(
            harness.observer,
            ValueError("test failure"),
            source="test",
            context_id="ctx-1",
            code="TEST_ERROR",
        )
        events = await harness.observer.list_recent(context_id="ctx-1", limit=5)
        assert any(e.event_type == AuditEventType.ERROR for e in events)
        assert any("test failure" in e.message for e in events)
    finally:
        await harness.shutdown()


async def test_spawn_pipeline_marks_failed_on_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = Harness(
        settings=get_settings().model_copy(
            update={
                "use_in_memory_bus": True,
                "use_fake_llm": True,
                "log_level": "WARNING",
            }
        )
    )
    await harness.startup()
    objective_id = "fail-pipeline"

    async def boom(_statement: str, *, objective_id: str | None = None, context_id: str | None = None):
        raise RuntimeError("pipeline exploded")

    monkeypatch.setattr(harness, "run_pipeline", boom)
    harness.track_pipeline(objective_id, "test idea")
    harness.spawn_pipeline("test idea", objective_id)
    await asyncio.sleep(0.1)
    try:
        assert harness._pipelines[objective_id]["status"] == "failed"
        assert "pipeline exploded" in harness._pipelines[objective_id]["error"]
        events = await harness.observer.list_recent(context_id=objective_id, limit=10)
        assert any(e.event_type == AuditEventType.ERROR for e in events)

        state = await harness.get_pipeline(objective_id)
        assert state is not None
        assert "pipeline exploded" in state["error"]
    finally:
        await harness.shutdown()
