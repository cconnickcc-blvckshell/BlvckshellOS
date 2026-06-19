"""Tests for chat attachments API."""

from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient

from harness.config import get_settings


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


def test_chat_accepts_attachments_without_message(client: TestClient) -> None:
    data = base64.b64encode(b"hello attachment").decode()
    resp = client.post(
        "/chat",
        json={
            "message": "",
            "attachments": [
                {
                    "type": "document",
                    "filename": "note.txt",
                    "media_type": "text/plain",
                    "data": data,
                }
            ],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["session_id"]


def test_chat_requires_message_or_attachments(client: TestClient) -> None:
    resp = client.post("/chat", json={"message": ""})
    assert resp.status_code == 422
