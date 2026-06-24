"""Integration tests for the harness FastAPI app over HTTP.

These exercise the full app lifespan (which boots a real in-memory harness),
intake, pipeline tracking, registry, ledger, doctrine, and the observer events
endpoint.
"""

from __future__ import annotations

import base64

import httpx
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
    # Worker brains register; the orchestrator (formerly "ckos") is not a brain.
    assert {"venture", "commander", "capital", "blvckbot"}.issubset(ids)
    assert "ckos" not in ids
    assert "orchestrator" not in ids


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


def test_fiverr_lead_submit_and_list(client: TestClient) -> None:
    resp = client.post(
        "/leads/fiverr",
        json={
            "title": "Need a logo redesign",
            "description": "Modern minimalist logo for a coffee brand",
            "budget": 250,
            "factors": {"fit": 8, "profitability": 6, "client_quality": 7},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "fiverr_manual"
    assert body["score"] == 7.0

    listed = client.get("/leads")
    assert listed.status_code == 200
    assert any(lead["title"] == "Need a logo redesign" for lead in listed.json())


def test_fiverr_lead_requires_title_or_description(client: TestClient) -> None:
    resp = client.post("/leads/fiverr", json={"budget": 100})
    assert resp.status_code == 422


def test_approvals_endpoint_surfaces_needs_operator_results(client: TestClient) -> None:
    resp = client.get("/approvals")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_approvals_endpoint_lists_pending_human_gate_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A human-gated brain task should show up in /approvals until resolved."""
    from harness.schemas.message import HarnessMessage, MessageType
    from harness.schemas.task import Task

    monkeypatch.setenv("BLVCKSHELL_USE_IN_MEMORY_BUS", "true")
    monkeypatch.setenv("BLVCKSHELL_USE_FAKE_LLM", "true")
    monkeypatch.setenv("BLVCKSHELL_LOG_LEVEL", "WARNING")
    get_settings.cache_clear()

    from harness.api import main as api_main

    app = api_main.create_app()
    async with app.router.lifespan_context(app):
        harness = api_main.get_harness()
        brain = harness.get_worker("ops")
        task = Task(
            run_id="approvals-test",
            objective_id="approvals-test",
            capability="financial_action_flagging",
            objective="Flag the month-end payout for review.",
            inputs={},
        )
        message = HarnessMessage(
            source="test",
            destination=brain.brain_id,
            message_type=MessageType.TASK,
            payload=task.model_dump(mode="json"),
            context_id="approvals-test",
        )
        await brain.handle_task(message)

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/approvals")
            assert resp.status_code == 200
            body = resp.json()
            assert len(body) >= 1
            assert all(e["outcome"] is None for e in body)
            assert all("judgment_outcome:REQUEST_MORE_EVIDENCE" in e["assumptions"] for e in body)

    get_settings.cache_clear()


def test_cors_restricted_when_frontend_url_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLVCKSHELL_USE_IN_MEMORY_BUS", "true")
    monkeypatch.setenv("BLVCKSHELL_USE_FAKE_LLM", "true")
    monkeypatch.setenv("BLVCKSHELL_LOG_LEVEL", "WARNING")
    monkeypatch.setenv("BLVCKSHELL_FRONTEND_URL", "https://blvckshell.vercel.app")
    get_settings.cache_clear()

    from harness.api.main import create_app

    with TestClient(create_app()) as cors_client:
        resp = cors_client.options(
            "/health",
            headers={
                "Origin": "https://blvckshell.vercel.app",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.headers.get("access-control-allow-origin") == "https://blvckshell.vercel.app"

    get_settings.cache_clear()
