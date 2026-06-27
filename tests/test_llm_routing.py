"""Tests for multi-provider LLM routing and per-brain model config."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from harness.config import Settings
from harness.core.agent_loop import AgentLoop
from harness.core.llm import (
    FakeLLMClient,
    LLMError,
    LLMResponse,
    MultiProviderLLMClient,
    OllamaClient,
    build_llm_client,
    resolve_provider,
)
from harness.core.observer import InMemoryAuditStore, Observer
from harness.schemas.audit import AuditEventType
from harness.schemas.brain_info import BrainContext
from harness.schemas.task import Task
from judgment.lifecycle import JudgmentLifecycle
from judgment.profile import JudgmentProfile, ModelConfig
from judgment.traces import LifecycleRunContext


def test_resolve_provider_auto_detection() -> None:
    assert resolve_provider("claude-sonnet-4-6") == "anthropic"
    assert resolve_provider("gpt-4o") == "openai"
    assert resolve_provider("o1-preview") == "openai"
    assert resolve_provider("o3-mini") == "openai"
    assert resolve_provider("qwen2.5:72b") == "ollama"
    assert resolve_provider("llama3.2") == "ollama"


def test_resolve_provider_explicit_override() -> None:
    assert resolve_provider("gpt-4o", "anthropic") == "anthropic"


def test_build_llm_client_fake_when_no_keys() -> None:
    settings = Settings(
        use_fake_llm=False,
        anthropic_api_key=None,
        openai_api_key=None,
        ollama_base_url=None,
    )
    client = build_llm_client(settings)
    assert isinstance(client, FakeLLMClient)


def test_build_llm_client_fake_when_forced() -> None:
    client = build_llm_client(Settings(use_fake_llm=True, anthropic_api_key="sk-test"))
    assert isinstance(client, FakeLLMClient)


def test_build_llm_client_ollama_only() -> None:
    # Even a single provider is wrapped in the multiplexer so declared
    # fallback_models are honored; the lone ollama client is what it routes to.
    client = build_llm_client(
        Settings(
            use_fake_llm=False,
            anthropic_api_key=None,
            openai_api_key=None,
            ollama_base_url="http://localhost:11434",
        )
    )
    assert isinstance(client, MultiProviderLLMClient)
    assert isinstance(client._clients["ollama"], OllamaClient)


def test_build_llm_client_single_anthropic_honors_fallback_chain() -> None:
    # With only the Anthropic key, the client must still route through the
    # multiplexer (not a bare AnthropicClient) so fallback_models are honored
    # the moment a second provider key is added — no code change required.
    client = build_llm_client(
        Settings(use_fake_llm=False, anthropic_api_key="sk-ant", openai_api_key=None)
    )
    assert isinstance(client, MultiProviderLLMClient)


def test_build_llm_client_multi_when_multiple_keys() -> None:
    client = build_llm_client(
        Settings(
            use_fake_llm=False,
            anthropic_api_key="sk-ant",
            openai_api_key="sk-openai",
            ollama_base_url="http://localhost:11434",
        )
    )
    assert isinstance(client, MultiProviderLLMClient)


@pytest.mark.asyncio
async def test_multi_provider_fallback_on_failure() -> None:
    primary = FakeLLMClient()
    fallback = FakeLLMClient()

    async def boom(**_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("provider down")

    primary.complete = boom  # type: ignore[method-assign]

    router = MultiProviderLLMClient(
        clients={"anthropic": primary, "openai": fallback},
        default_provider="anthropic",
        default_models={"anthropic": "claude-sonnet-4-6", "openai": "gpt-4o"},
    )
    resp = await router.complete(
        system="sys",
        messages=[{"role": "user", "content": "hi"}],
        model_override="claude-sonnet-4-6",
        fallback_models=["gpt-4o"],
    )
    assert resp.model == "gpt-4o"
    assert len(fallback.calls) == 1


@pytest.mark.asyncio
async def test_multi_provider_raises_when_all_fail() -> None:
    primary = FakeLLMClient()

    async def boom(**_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("down")

    primary.complete = boom  # type: ignore[method-assign]
    router = MultiProviderLLMClient(
        clients={"anthropic": primary},
        default_provider="anthropic",
        default_models={"anthropic": "claude-sonnet-4-6"},
    )
    with pytest.raises(LLMError, match="All providers failed"):
        await router.complete(
            system="sys",
            messages=[{"role": "user", "content": "hi"}],
            model_override="claude-sonnet-4-6",
        )


@pytest.mark.asyncio
async def test_agent_loop_passes_per_brain_model_config() -> None:
    llm = FakeLLMClient()
    cfg = ModelConfig(preferred_model="claude-sonnet-4-6", temperature=0.2, max_tokens=512)
    loop = AgentLoop(llm=llm, tools=[], model_config=cfg)
    await loop.run(
        brain_id="venture",
        context_id="run-1",
        system_prompt="sys",
        user_prompt="analyze",
    )
    assert llm.calls[0]["model_override"] == "claude-sonnet-4-6"
    assert llm.calls[0]["temperature"] == 0.2
    assert llm.calls[0]["max_tokens"] == 512


@pytest.mark.asyncio
async def test_local_model_config_routes_to_ollama() -> None:
    cfg = ModelConfig(preferred_model="qwen2.5:72b", local=True, temperature=0.5)
    settings = Settings(ollama_base_url="http://ollama.local:11434")
    mock_response = LLMResponse(text="local ok", model="qwen2.5:72b", provider="ollama")

    with patch.object(OllamaClient, "complete", new_callable=AsyncMock) as mock_complete:
        mock_complete.return_value = mock_response
        loop = AgentLoop(
            llm=FakeLLMClient(),
            model_config=cfg,
            settings=settings,
        )
        result = await loop.run(
            brain_id="worker",
            context_id="run-1",
            system_prompt="sys",
            user_prompt="task",
        )

    mock_complete.assert_awaited_once()
    call_kwargs = mock_complete.await_args.kwargs
    assert call_kwargs["model_override"] == "qwen2.5:72b"
    assert result.metrics["provider"] == "ollama"
    assert result.metrics["model_used"] == "qwen2.5:72b"


@pytest.mark.asyncio
async def test_evidence_stage_includes_model_used_in_observer() -> None:
    observer = Observer(InMemoryAuditStore())
    await observer.connect()

    cfg = ModelConfig(preferred_model="gpt-4o")
    llm = FakeLLMClient()
    loop = AgentLoop(llm=llm, model_config=cfg, observer=observer)

    async def gather():
        return await loop.run(
            brain_id="venture",
            context_id="ctx-1",
            system_prompt="sys",
            user_prompt="go proceed with the plan",
        )

    lifecycle = JudgmentLifecycle()
    await lifecycle.run(
        brain_id="venture",
        context_id="ctx-1",
        task=Task(capability="test", objective="go proceed", assigned_brain="venture"),
        context=BrainContext(context_id="ctx-1", brain_id="venture"),
        profile=JudgmentProfile(domain="venture", model=cfg),
        gather_evidence=gather,
        observer=observer,
        run_context=LifecycleRunContext(),
    )

    events = await observer.list_recent(context_id="ctx-1", limit=50)
    evidence_events = [
        e
        for e in events
        if e.event_type == AuditEventType.JUDGMENT_STAGE_COMPLETED
        and e.data.get("stage") == "EVIDENCE"
    ]
    assert evidence_events, "expected EVIDENCE stage audit event"
    output = evidence_events[0].data.get("output", {})
    assert output.get("model_used") == "gpt-4o"
    assert output.get("provider") == "fake"


@pytest.mark.asyncio
async def test_fake_llm_records_model_override() -> None:
    llm = FakeLLMClient()
    await llm.complete(
        system="s",
        messages=[{"role": "user", "content": "x"}],
        model_override="claude-sonnet-4-6",
    )
    assert llm.calls[0]["model_override"] == "claude-sonnet-4-6"
