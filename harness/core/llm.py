"""LLM client abstraction.

Brains never import vendor SDKs directly; they call an :class:`LLMClient`. Providers:

- :class:`AnthropicClient` — Claude
- :class:`OpenAIClient` — GPT / o-series (optional ``openai`` package)
- :class:`OllamaClient` — local models
- :class:`FakeLLMClient` — deterministic offline fallback
- :class:`MultiProviderLLMClient` — routes by model name with fallback chains

All return a uniform :class:`LLMResponse` carrying text, tool calls, and metrics.
"""

from __future__ import annotations

import abc
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from harness.logging_config import get_logger

logger = get_logger("llm")


class LLMError(Exception):
    """Raised when every provider in a fallback chain fails."""


@dataclass(slots=True)
class ToolCall:
    """A single tool invocation requested by the model."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(slots=True)
class LLMResponse:
    """A uniform response from any LLM backend."""

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    model: str = "unknown"
    provider: str = "unknown"
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    stop_reason: str = "end_turn"

    @property
    def wants_tools(self) -> bool:
        """Whether the model requested any tool calls."""
        return bool(self.tool_calls)

    def metrics(self) -> dict[str, Any]:
        """Return a metrics dict suitable for audit/result records."""
        return {
            "model": self.model,
            "model_used": self.model,
            "provider": self.provider,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": round(self.cost_usd, 6),
            "latency_ms": round(self.latency_ms, 2),
        }


def resolve_provider(model: str, explicit_provider: str | None = None) -> str:
    """Auto-detect provider from model name when not explicit."""
    if explicit_provider:
        return explicit_provider
    lower = model.lower()
    if lower.startswith("claude"):
        return "anthropic"
    if lower.startswith("gpt") or lower.startswith("o1") or lower.startswith("o3"):
        return "openai"
    return "ollama"


class LLMClient(abc.ABC):
    """Abstract chat-completion client with tool support."""

    @abc.abstractmethod
    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        model_override: str | None = None,
        fallback_models: list[str] | None = None,
        temperature: float | None = None,
        max_tokens: int = 2048,
        provider_override: str | None = None,
    ) -> LLMResponse:
        """Produce a completion."""


# Rough Claude 3.5 Sonnet pricing (USD per token).
_CLAUDE_INPUT_COST = 3.0 / 1_000_000
_CLAUDE_OUTPUT_COST = 15.0 / 1_000_000
# Rough GPT-4o pricing (USD per token).
_GPT4O_INPUT_COST = 2.5 / 1_000_000
_GPT4O_OUTPUT_COST = 10.0 / 1_000_000


def _chosen_model(model: str | None, model_override: str | None, default: str) -> str:
    return model_override or model or default


class AnthropicClient(LLMClient):
    """Claude-backed client using the Anthropic Messages API."""

    provider = "anthropic"

    def __init__(self, api_key: str, default_model: str) -> None:
        self._api_key = api_key
        self._default_model = default_model
        self._client = None  # type: ignore[assignment]

    def _require(self):  # type: ignore[no-untyped-def]
        if self._client is None:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=self._api_key)
        return self._client

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        model_override: str | None = None,
        fallback_models: list[str] | None = None,
        temperature: float | None = None,
        max_tokens: int = 2048,
        provider_override: str | None = None,
    ) -> LLMResponse:
        chosen = _chosen_model(model, model_override, self._default_model)
        started = time.perf_counter()
        kwargs: dict[str, Any] = {
            "model": chosen,
            "system": system,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
        if temperature is not None:
            kwargs["temperature"] = temperature
        resp = await self._require().messages.create(**kwargs)
        latency_ms = (time.perf_counter() - started) * 1000

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, arguments=dict(block.input))
                )

        in_tok = resp.usage.input_tokens
        out_tok = resp.usage.output_tokens
        return LLMResponse(
            text="\n".join(text_parts),
            tool_calls=tool_calls,
            model=chosen,
            provider=self.provider,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=in_tok * _CLAUDE_INPUT_COST + out_tok * _CLAUDE_OUTPUT_COST,
            latency_ms=latency_ms,
            stop_reason=resp.stop_reason or "end_turn",
        )


class OpenAIClient(LLMClient):
    """OpenAI chat-completions client (GPT / o-series)."""

    provider = "openai"

    def __init__(self, api_key: str, default_model: str) -> None:
        self._api_key = api_key
        self._default_model = default_model
        self._client = None  # type: ignore[assignment]

    def _require(self):  # type: ignore[no-untyped-def]
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError as exc:
                raise LLMError(
                    "openai package is not installed; run: poetry install -E openai"
                ) from exc
            self._client = AsyncOpenAI(api_key=self._api_key)
        return self._client

    @staticmethod
    def _to_openai_tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
        if not tools:
            return None
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
                },
            }
            for t in tools
        ]

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        model_override: str | None = None,
        fallback_models: list[str] | None = None,
        temperature: float | None = None,
        max_tokens: int = 2048,
        provider_override: str | None = None,
    ) -> LLMResponse:
        chosen = _chosen_model(model, model_override, self._default_model)
        started = time.perf_counter()
        oai_messages: list[dict[str, Any]] = [{"role": "system", "content": system}, *messages]
        kwargs: dict[str, Any] = {
            "model": chosen,
            "messages": oai_messages,
            "max_tokens": max_tokens,
        }
        oai_tools = self._to_openai_tools(tools)
        if oai_tools:
            kwargs["tools"] = oai_tools
        if temperature is not None:
            kwargs["temperature"] = temperature

        resp = await self._require().chat.completions.create(**kwargs)
        latency_ms = (time.perf_counter() - started) * 1000
        choice = resp.choices[0].message

        tool_calls: list[ToolCall] = []
        if choice.tool_calls:
            for tc in choice.tool_calls:
                import json

                args = tc.function.arguments
                if isinstance(args, str):
                    args = json.loads(args) if args else {}
                tool_calls.append(
                    ToolCall(id=tc.id, name=tc.function.name, arguments=dict(args))
                )

        in_tok = resp.usage.prompt_tokens if resp.usage else 0
        out_tok = resp.usage.completion_tokens if resp.usage else 0
        return LLMResponse(
            text=choice.content or "",
            tool_calls=tool_calls,
            model=chosen,
            provider=self.provider,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=in_tok * _GPT4O_INPUT_COST + out_tok * _GPT4O_OUTPUT_COST,
            latency_ms=latency_ms,
            stop_reason="tool_use" if tool_calls else "end_turn",
        )


class OllamaClient(LLMClient):
    """Local-model client backed by an Ollama server."""

    provider = "ollama"

    def __init__(self, base_url: str, default_model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._default_model = default_model

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        model_override: str | None = None,
        fallback_models: list[str] | None = None,
        temperature: float | None = None,
        max_tokens: int = 2048,
        provider_override: str | None = None,
    ) -> LLMResponse:
        import httpx

        chosen = _chosen_model(model, model_override, self._default_model)
        options: dict[str, Any] = {"num_predict": max_tokens}
        if temperature is not None:
            options["temperature"] = temperature
        payload = {
            "model": chosen,
            "stream": False,
            "options": options,
            "messages": [{"role": "system", "content": system}, *messages],
        }
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{self._base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
        latency_ms = (time.perf_counter() - started) * 1000
        return LLMResponse(
            text=data.get("message", {}).get("content", ""),
            model=chosen,
            provider=self.provider,
            input_tokens=data.get("prompt_eval_count", 0),
            output_tokens=data.get("eval_count", 0),
            cost_usd=0.0,
            latency_ms=latency_ms,
            stop_reason="end_turn",
        )


class FakeLLMClient(LLMClient):
    """Deterministic offline client for tests and no-key operation."""

    provider = "fake"

    def __init__(
        self,
        *,
        scripted: list[LLMResponse] | None = None,
        responder: Callable[[str, list[dict[str, Any]]], LLMResponse] | None = None,
    ) -> None:
        self._scripted = list(scripted or [])
        self._responder = responder
        self.calls: list[dict[str, Any]] = []

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        model_override: str | None = None,
        fallback_models: list[str] | None = None,
        temperature: float | None = None,
        max_tokens: int = 2048,
        provider_override: str | None = None,
    ) -> LLMResponse:
        chosen = _chosen_model(model, model_override, "fake-llm")
        self.calls.append(
            {
                "system": system,
                "messages": list(messages),
                "model_override": model_override or model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "provider_override": provider_override,
                "fallback_models": fallback_models,
            }
        )
        if self._scripted:
            resp = self._scripted.pop(0)
            if resp.model == "unknown":
                resp.model = chosen
            resp.provider = self.provider
            return resp
        if self._responder is not None:
            resp = self._responder(system, messages)
            resp.provider = self.provider
            return resp

        last_user = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                last_user = content if isinstance(content, str) else str(content)
                break
        summary = last_user.strip().replace("\n", " ")[:240]
        text = f"[offline-analysis] Reviewed the request and produced a structured plan: {summary}"
        return LLMResponse(
            text=text,
            model=chosen,
            provider=self.provider,
            input_tokens=len(system) // 4 + len(last_user) // 4,
            output_tokens=len(text) // 4,
            cost_usd=0.0,
            latency_ms=0.1,
        )


class MultiProviderLLMClient(LLMClient):
    """Routes to the right provider by model name; falls back on failure."""

    provider = "multi"

    def __init__(
        self,
        *,
        clients: dict[str, LLMClient],
        default_provider: str,
        default_models: dict[str, str],
    ) -> None:
        self._clients = clients
        self._default_provider = default_provider
        self._default_models = default_models

    def _resolve_provider(self, model: str, explicit_provider: str | None) -> str:
        return resolve_provider(model, explicit_provider)

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        model_override: str | None = None,
        fallback_models: list[str] | None = None,
        temperature: float | None = None,
        max_tokens: int = 2048,
        provider_override: str | None = None,
    ) -> LLMResponse:
        default_model = self._default_models.get(self._default_provider, "unknown")
        primary = model_override or model or default_model
        chain = [primary, *(fallback_models or [])]
        errors: list[str] = []

        for attempt_model in chain:
            attempt_provider = self._resolve_provider(attempt_model, provider_override)
            client = self._clients.get(attempt_provider)
            if client is None:
                errors.append(f"{attempt_provider}: not configured")
                continue
            try:
                return await client.complete(
                    system=system,
                    messages=messages,
                    tools=tools,
                    model_override=attempt_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    provider_override=provider_override,
                )
            except Exception as exc:
                logger.warning(
                    "llm_provider_failed",
                    model=attempt_model,
                    provider=attempt_provider,
                    error=str(exc),
                )
                errors.append(f"{attempt_model}@{attempt_provider}: {exc}")
                continue

        raise LLMError(f"All providers failed: {errors}")


def build_llm_client(settings: Any) -> LLMClient:
    """Construct the configured LLM client from settings."""
    if settings.use_fake_llm:
        return FakeLLMClient()

    clients: dict[str, LLMClient] = {}
    default_models: dict[str, str] = {}

    if settings.anthropic_api_key:
        clients["anthropic"] = AnthropicClient(
            settings.anthropic_api_key, settings.anthropic_model
        )
        default_models["anthropic"] = settings.anthropic_model

    if settings.openai_api_key:
        clients["openai"] = OpenAIClient(settings.openai_api_key, settings.openai_model)
        default_models["openai"] = settings.openai_model

    ollama_url = settings.ollama_effective_url
    if ollama_url:
        clients["ollama"] = OllamaClient(ollama_url, settings.ollama_model)
        default_models["ollama"] = settings.ollama_model

    if not clients:
        logger.warning("llm_fallback_to_fake", reason="no_providers_configured")
        return FakeLLMClient()

    if len(clients) == 1:
        return next(iter(clients.values()))

    default_provider = next(k for k in ("anthropic", "openai", "ollama") if k in clients)
    return MultiProviderLLMClient(
        clients=clients,
        default_provider=default_provider,
        default_models=default_models,
    )
