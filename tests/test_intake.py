"""Tests for the intake layer (text normalization + API)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from harness.api.main import create_app
from intake.text import normalize_text
from intake.voice import StubTranscriber


def test_normalize_collapses_whitespace() -> None:
    assert normalize_text("  build   a\n\nthing  ") == "build a thing"


def test_normalize_rejects_empty() -> None:
    with pytest.raises(ValueError):
        normalize_text("   ")


async def test_stub_transcriber_returns_placeholder() -> None:
    text = await StubTranscriber().transcribe(b"1234")
    assert "voice capture" in text


def test_api_intake_and_pipeline_roundtrip() -> None:
    # Exercises the real ASGI app with the in-memory backends end to end.
    app = create_app()
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200

        resp = client.post("/intake", json={"text": "launch a podcast"}, params={"wait": True})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "completed"
        assert body["result"]["status"] == "success"

        pipeline_id = body["pipeline_id"]
        pipeline = client.get(f"/pipelines/{pipeline_id}").json()
        assert pipeline["result"] is not None
        assert pipeline["events"]

        brains = client.get("/brains").json()["brains"]
        assert {b["brain_id"] for b in brains} >= {"ckos", "venture", "commander", "capital"}

        judgments = client.get("/judgments").json()["judgments"]
        assert judgments
