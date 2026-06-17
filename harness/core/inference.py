"""Inference layer — a uniform async LLM client across providers.

Three providers behind one interface:

* ``stub`` — deterministic, offline. Powers tests and zero-key local bring-up.
* ``anthropic`` — Claude, the primary inference for most brains.
* ``ollama`` — local Qwen for cost-free lightweight tasks.

Tool schemas use the Anthropic shape; the stub and Ollama providers adapt to it.
"""

from __future__ import annotations

import abc
import json
import time
from typing import Any

from pydantic import BaseModel, Field

from harness.config import settings
from harness.core.logging import get_logger

logger = get_logger(__name__)


class LLMMessage(BaseModel):
    """A single conversation turn handed to the model."""

    role: str
    content: str


class ToolCall(BaseModel):
    """A model-requested tool invocation."""

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    """A normalized model response across providers.

    Attributes:
        content: The assistant text.
        tool_calls: Any requested tool invocations.
        usage: Token/cost/latency accounting.
        model: The model that produced the response.
        stop_reason: Why generation stopped.
    """

    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: dict[str, Any] = Field(default_factory=dict)
    model: str = ""
    stop_reason: str = "stop"


class LLMClient(abc.ABC):
    """Abstract async LLM client."""

    model: str

    @abc.abstractmethod
    async def complete(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Generate a completion.

        Args:
            system: System prompt establishing the brain's role.
            messages: Conversation so far.
            tools: Optional tool schemas (Anthropic shape) the model may call.

        Returns:
            A normalized :class:`LLMResponse`.
        """


class StubLLMClient(LLMClient):
    """Deterministic offline client for tests and keyless local runs.

    It never calls tools and produces a concise, structured echo of the most
    recent user content so pipelines can be exercised end to end without a key.
    """

    def __init__(self, model: str = "stub-1") -> None:
        """Create the stub client with a synthetic model name."""
        self.model = model

    async def complete(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Return a deterministic synthesis of the latest user message."""
        start = time.perf_counter()
        last_user = next(
            (m.content for m in reversed(messages) if m.role == "user"),
            "",
        )
        role_hint = system.strip().splitlines()[0] if system.strip() else "assistant"
        content = (
            f"[stub:{self.model}] Acknowledged as '{role_hint[:60]}'. "
            f"Processed objective: {last_user[:280].strip()}"
        )
        latency_ms = (time.perf_counter() - start) * 1000
        prompt_tokens = sum(len(m.content.split()) for m in messages) + len(system.split())
        completion_tokens = len(content.split())
        return LLMResponse(
            content=content,
            tool_calls=[],
            model=self.model,
            stop_reason="stop",
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "cost_usd": 0.0,
                "latency_ms": round(latency_ms, 3),
            },
        )


class AnthropicLLMClient(LLMClient):
    """Claude client using the official async Anthropic SDK."""

    def __init__(self, api_key: str, model: str) -> None:
        """Store credentials and model; the client is created on first call."""
        self._api_key = api_key
        self.model = model
        self._client: Any | None = None

    def _ensure_client(self) -> Any:
        """Lazily construct the async Anthropic client."""
        if self._client is None:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=self._api_key)
        return self._client

    async def complete(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Call Claude and normalize the response, including tool use."""
        client = self._ensure_client()
        start = time.perf_counter()
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": settings.llm_max_tokens,
            "temperature": settings.llm_temperature,
            "system": system,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if tools:
            payload["tools"] = tools
        response = await client.messages.create(**payload)
        latency_ms = (time.perf_counter() - start) * 1000

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, arguments=dict(block.input))
                )
        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "input_tokens", 0) if usage else 0
        completion_tokens = getattr(usage, "output_tokens", 0) if usage else 0
        return LLMResponse(
            content="\n".join(text_parts),
            tool_calls=tool_calls,
            model=self.model,
            stop_reason=response.stop_reason or "stop",
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "latency_ms": round(latency_ms, 3),
            },
        )


class OllamaLLMClient(LLMClient):
    """Local Ollama client (e.g. Qwen 14B) over HTTP."""

    def __init__(self, base_url: str, model: str) -> None:
        """Store the Ollama endpoint and model name."""
        self._base_url = base_url.rstrip("/")
        self.model = model

    async def complete(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Call the Ollama chat endpoint and normalize the response."""
        import httpx

        start = time.perf_counter()
        chat_messages = [{"role": "system", "content": system}]
        chat_messages += [{"role": m.role, "content": m.content} for m in messages]
        body: dict[str, Any] = {
            "model": self.model,
            "messages": chat_messages,
            "stream": False,
            "options": {"temperature": settings.llm_temperature},
        }
        if tools:
            body["tools"] = tools
        async with httpx.AsyncClient(timeout=120.0) as http:
            res = await http.post(f"{self._base_url}/api/chat", json=body)
            res.raise_for_status()
            data = res.json()
        latency_ms = (time.perf_counter() - start) * 1000

        message = data.get("message", {})
        tool_calls = [
            ToolCall(
                id=f"ollama-{i}",
                name=call["function"]["name"],
                arguments=_coerce_args(call["function"].get("arguments", {})),
            )
            for i, call in enumerate(message.get("tool_calls", []) or [])
        ]
        return LLMResponse(
            content=message.get("content", ""),
            tool_calls=tool_calls,
            model=self.model,
            stop_reason=data.get("done_reason", "stop"),
            usage={
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
                "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
                "latency_ms": round(latency_ms, 3),
            },
        )


def _coerce_args(args: Any) -> dict[str, Any]:
    """Coerce tool-call arguments into a dict (Ollama may return a string)."""
    if isinstance(args, dict):
        return args
    if isinstance(args, str):
        try:
            return json.loads(args)
        except json.JSONDecodeError:
            return {"_raw": args}
    return {}


def create_llm_client(model: str | None = None) -> LLMClient:
    """Construct the configured LLM client.

    Args:
        model: Optional model override for the selected provider.

    Returns:
        A provider-specific :class:`LLMClient`. Falls back to the stub when the
        selected provider is missing required configuration.
    """
    provider = settings.inference_provider
    if provider == "anthropic" and settings.anthropic_api_key:
        return AnthropicLLMClient(settings.anthropic_api_key, model or settings.anthropic_model)
    if provider == "ollama":
        return OllamaLLMClient(settings.ollama_base_url, model or settings.ollama_model)
    if provider == "anthropic":
        logger.warning("Anthropic selected but no API key set; using stub client")
    return StubLLMClient(model or "stub-1")
