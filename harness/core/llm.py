"""LLM client abstraction.

Brains never import vendor SDKs directly; they call an :class:`LLMClient`. Three
implementations are provided:

- :class:`AnthropicClient` — Claude, the primary inference engine.
- :class:`OllamaClient` — local models (e.g. Qwen 14B) for cost-free work.
- :class:`FakeLLMClient` — deterministic, offline, used for tests and for
  running the whole harness without any API keys.

All return a uniform :class:`LLMResponse` carrying text, any tool calls, and
usage metrics (model, tokens, cost, latency) for the Observer.
"""

from __future__ import annotations

import abc
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from harness.logging_config import get_logger

logger = get_logger("llm")


@dataclass(slots=True)
class ToolCall:
    """A single tool invocation requested by the model.

    Attributes:
        id: Provider-assigned identifier for correlating the result.
        name: The tool name to invoke.
        arguments: The arguments object for the tool.
    """

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(slots=True)
class LLMResponse:
    """A uniform response from any LLM backend.

    Attributes:
        text: The assistant's natural-language text, if any.
        tool_calls: Tool invocations the model requested, if any.
        model: The model id that produced the response.
        input_tokens: Prompt tokens consumed.
        output_tokens: Completion tokens produced.
        cost_usd: Estimated cost in USD.
        latency_ms: Wall-clock latency of the call.
        stop_reason: Why generation stopped.
    """

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    model: str = "unknown"
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
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": round(self.cost_usd, 6),
            "latency_ms": round(self.latency_ms, 2),
        }


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
        max_tokens: int = 2048,
    ) -> LLMResponse:
        """Produce a completion.

        Args:
            system: The system prompt.
            messages: Chat messages in ``{"role", "content"}`` form.
            tools: Optional tool schemas the model may call.
            model: Optional model override.
            max_tokens: Maximum completion tokens.

        Returns:
            A uniform :class:`LLMResponse`.
        """


# Rough Claude 3.5 Sonnet pricing (USD per token) for cost estimation.
_CLAUDE_INPUT_COST = 3.0 / 1_000_000
_CLAUDE_OUTPUT_COST = 15.0 / 1_000_000


class AnthropicClient(LLMClient):
    """Claude-backed client using the Anthropic Messages API."""

    def __init__(self, api_key: str, default_model: str) -> None:
        """Create the client.

        Args:
            api_key: Anthropic API key.
            default_model: Model id used when a call omits ``model``.
        """
        self._api_key = api_key
        self._default_model = default_model
        self._client = None  # type: ignore[assignment]

    def _require(self):  # type: ignore[no-untyped-def]
        """Return a lazily-constructed async Anthropic client."""
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
        max_tokens: int = 2048,
    ) -> LLMResponse:
        """Call the Anthropic Messages API and normalize the response."""
        chosen = model or self._default_model
        started = time.perf_counter()
        kwargs: dict[str, Any] = {
            "model": chosen,
            "system": system,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
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
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=in_tok * _CLAUDE_INPUT_COST + out_tok * _CLAUDE_OUTPUT_COST,
            latency_ms=latency_ms,
            stop_reason=resp.stop_reason or "end_turn",
        )


class OllamaClient(LLMClient):
    """Local-model client backed by an Ollama server (cost-free inference)."""

    def __init__(self, base_url: str, default_model: str) -> None:
        """Create the client.

        Args:
            base_url: The Ollama base URL.
            default_model: Default local model id.
        """
        self._base_url = base_url.rstrip("/")
        self._default_model = default_model

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        """Call the Ollama chat API and normalize the response."""
        import httpx

        chosen = model or self._default_model
        payload = {
            "model": chosen,
            "stream": False,
            "options": {"num_predict": max_tokens},
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
            input_tokens=data.get("prompt_eval_count", 0),
            output_tokens=data.get("eval_count", 0),
            cost_usd=0.0,
            latency_ms=latency_ms,
            stop_reason="end_turn",
        )


class FakeLLMClient(LLMClient):
    """Deterministic offline client for tests and no-key operation.

    By default it echoes a concise summary of the last user message. Optionally,
    a ``responder`` callback can compute responses, or a queue of scripted
    responses can be supplied for exercising multi-turn tool loops.
    """

    def __init__(
        self,
        *,
        scripted: list[LLMResponse] | None = None,
        responder: Callable[[str, list[dict[str, Any]]], LLMResponse] | None = None,
    ) -> None:
        """Create the fake client.

        Args:
            scripted: Optional FIFO of responses returned one per call.
            responder: Optional callback ``(system, messages) -> LLMResponse``.
        """
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
        max_tokens: int = 2048,
    ) -> LLMResponse:
        """Return the next scripted/responder/default response deterministically."""
        self.calls.append({"system": system, "messages": list(messages)})
        if self._scripted:
            resp = self._scripted.pop(0)
            if resp.model == "unknown":
                resp.model = model or "fake-llm"
            return resp
        if self._responder is not None:
            return self._responder(system, messages)

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
            model=model or "fake-llm",
            input_tokens=len(system) // 4 + len(last_user) // 4,
            output_tokens=len(text) // 4,
            cost_usd=0.0,
            latency_ms=0.1,
        )


def build_llm_client(settings: Any) -> LLMClient:
    """Construct the configured LLM client.

    Prefers Anthropic when a key is present; falls back to the deterministic fake
    so the harness always runs, even with no credentials.

    Args:
        settings: A :class:`~harness.config.Settings` instance.

    Returns:
        A concrete :class:`LLMClient`.
    """
    if settings.anthropic_enabled:
        return AnthropicClient(settings.anthropic_api_key, settings.anthropic_model)
    logger.warning("llm_fallback_to_fake", reason="no_anthropic_key_or_fake_forced")
    return FakeLLMClient()
