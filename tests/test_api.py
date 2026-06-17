"""Integration tests for the harness FastAPI app over HTTP.

These exercise the full app lifespan (which boots a real in-memory harness),
intake, pipeline tracking, registry, ledger, doctrine, and the observer events
endpoint.
"""

from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient
from harness.config import get_settings


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Yield a TestClient with the harness forced fully offline."""
    monkeypatch.setenv("BLVCKSHELL_USE_IN_MEMORY_BUS", "true")
    monkeypatch.setenv("BLVCKSHELL_USE_FAKE_LLM", "true")
    monkeypatch.setenv("BLVCKSHELL_LOG_LEVEL", "WARNING")
    get_settings.cache_clear()

    from harness.api.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_brains_registered(client: TestClient) -> None:
    resp = client.get("/brains")
    assert resp.status_code == 200
    ids = {b["brain_id"] for b in resp.json()}
    assert {"ckos", "venture", "commander", "capital"}.issubset(ids)


def test_intake_sync_runs_full_pipeline(client: TestClient) -> None:
    resp = client.post(
        "/intake", json={"text": "build a trading AI that beats the market", "wait": True}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "COMPLETED"
    assert body["result"]["output"]
    assert len(body["result"]["tasks"]) == 3


def test_intake_async_returns_ack(client: TestClient) -> None:
    resp = client.post("/intake", json={"text": "launch a newsletter", "wait": False})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "running"
    assert body["message"] == "Got it, running."
    assert body["pipeline_id"]


def test_intake_rejects_empty_text(client: TestClient) -> None:
    resp = client.post("/intake", json={"text": "   ", "wait": False})
    assert resp.status_code == 422


def test_voice_intake(client: TestClient) -> None:
    audio = base64.b64encode(b"build an autonomous research agent").decode()
    resp = client.post("/intake/voice", json={"audio_base64": audio, "wait": True})
    assert resp.status_code == 200
    assert "research agent" in resp.json()["idea"]


def test_pipeline_tracking_and_lookup(client: TestClient) -> None:
    resp = client.post("/intake", json={"text": "design a logo system", "wait": True})
    pid = resp.json()["pipeline_id"]

    listed = client.get("/pipelines")
    assert any(p["pipeline_id"] == pid for p in listed.json())

    detail = client.get(f"/pipelines/{pid}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "COMPLETED"

    assert client.get("/pipelines/does-not-exist").status_code == 404


def test_ledger_and_doctrine_endpoints(client: TestClient) -> None:
    client.post("/intake", json={"text": "build a trading AI", "wait": True})
    ledger = client.get("/ledger")
    assert ledger.status_code == 200
    assert len(ledger.json()) >= 1
    assert client.get("/doctrine").status_code == 200


def test_observer_events_endpoint(client: TestClient) -> None:
    client.post("/intake", json={"text": "build a trading AI", "wait": True})
    events = client.get("/observer/events")
    assert events.status_code == 200
    assert len(events.json()) >= 1
