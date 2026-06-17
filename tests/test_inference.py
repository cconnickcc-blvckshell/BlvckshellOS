"""Tests for the inference layer (stub provider)."""

from __future__ import annotations

from harness.core.inference import LLMMessage, StubLLMClient, create_llm_client


async def test_stub_is_deterministic_and_offline() -> None:
    client = StubLLMClient()
    response = await client.complete(
        system="Venture Brain.",
        messages=[LLMMessage(role="user", content="validate this idea")],
    )
    assert "validate this idea" in response.content
    assert response.tool_calls == []
    assert response.usage["total_tokens"] > 0
    assert response.usage["cost_usd"] == 0.0


async def test_create_llm_client_defaults_to_stub() -> None:
    # With default settings (no anthropic key, provider=stub) we get the stub.
    client = create_llm_client()
    assert isinstance(client, StubLLMClient)
