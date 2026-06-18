"""The agent loop — the think / act / observe cycle every brain runs.

This is the engine that drives a single brain through one task:

    LOAD CONTEXT -> THINK (LLM) -> ACT (tools) -> OBSERVE (results)
    -> ITERATE until done -> EMIT RESULT

It is deliberately model-agnostic: it talks only to an
:class:`~harness.core.llm.LLMClient` and a list of
:class:`~brains._base.tools.BaseTool`. Every LLM call and tool call is reported
to the Observer so the whole trace is auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from brains._base.tools import BaseTool
from judgment.profile import ModelConfig

from harness.config import Settings
from harness.core.errors import format_exception, report_error
from harness.core.llm import LLMClient, LLMResponse, OllamaClient
from harness.core.observer import Observer
from harness.schemas.audit import AuditEventType


@dataclass(slots=True)
class AgentLoopResult:
    """The outcome of running the agent loop for one task."""

    final_text: str = ""
    iterations: int = 0
    tool_invocations: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    transcript: list[dict[str, Any]] = field(default_factory=list)


class AgentLoop:
    """Runs the bounded think/act/observe cycle for a brain."""

    def __init__(
        self,
        *,
        llm: LLMClient,
        tools: list[BaseTool] | None = None,
        observer: Observer | None = None,
        max_iterations: int = 6,
        model_config: ModelConfig | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._llm = llm
        self._tools = {tool.name: tool for tool in (tools or [])}
        self._observer = observer
        self._max_iterations = max_iterations
        self._model_config = model_config
        self._settings = settings

    async def run(
        self,
        *,
        brain_id: str,
        context_id: str,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
    ) -> AgentLoopResult:
        """Execute the loop until the model stops requesting tools."""
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt}]
        tool_schemas = [tool.to_schema() for tool in self._tools.values()] or None

        result = AgentLoopResult()
        total_in = total_out = 0
        total_cost = 0.0
        total_latency = 0.0
        last_model = "unknown"
        last_provider = "unknown"

        for _ in range(self._max_iterations):
            result.iterations += 1
            response = await self._think(
                brain_id=brain_id,
                context_id=context_id,
                system_prompt=system_prompt,
                messages=messages,
                tool_schemas=tool_schemas,
                model=model,
            )
            last_model = response.model
            last_provider = response.provider
            total_in += response.input_tokens
            total_out += response.output_tokens
            total_cost += response.cost_usd
            total_latency += response.latency_ms

            if not response.wants_tools:
                result.final_text = response.text
                break

            messages.append(self._assistant_tool_message(response))
            tool_results = await self._act(
                brain_id=brain_id, context_id=context_id, response=response, result=result
            )
            messages.append({"role": "user", "content": tool_results})
        else:
            result.final_text = result.final_text or "Reached iteration limit without completion."

        result.metrics = {
            "input_tokens": total_in,
            "output_tokens": total_out,
            "cost_usd": round(total_cost, 6),
            "latency_ms": round(total_latency, 2),
            "iterations": result.iterations,
            "tool_calls": len(result.tool_invocations),
            "model_used": last_model,
            "provider": last_provider,
            "tokens": total_in + total_out,
        }
        result.transcript = messages
        return result

    async def _think(
        self,
        *,
        brain_id: str,
        context_id: str,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tool_schemas: list[dict[str, Any]] | None,
        model: str | None,
    ) -> LLMResponse:
        """Perform one THINK step (a single LLM call) and audit it."""
        cfg = self._model_config
        model_override = None
        fallback_models: list[str] | None = None
        provider_override: str | None = None
        temperature: float | None = None
        max_tokens = 2048

        if cfg is not None:
            model_override = cfg.preferred_model
            fallback_models = list(cfg.fallback_models)
            provider_override = cfg.provider
            temperature = cfg.temperature
            max_tokens = cfg.max_tokens
        elif model is not None:
            model_override = model

        if cfg is not None and cfg.local:
            base_url = "http://localhost:11434"
            if self._settings is not None:
                base_url = self._settings.ollama_effective_url or base_url
            ollama = OllamaClient(base_url=base_url, default_model=cfg.preferred_model)
            try:
                response = await ollama.complete(
                    system=system_prompt,
                    messages=messages,
                    tools=tool_schemas,
                    model_override=cfg.preferred_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except Exception as exc:
                await self._report_llm_failure(brain_id, context_id, exc)
                raise
        else:
            try:
                response = await self._llm.complete(
                    system=system_prompt,
                    messages=messages,
                    tools=tool_schemas,
                    model=model,
                    model_override=model_override,
                    fallback_models=fallback_models,
                    provider_override=provider_override,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except Exception as exc:
                await self._report_llm_failure(brain_id, context_id, exc)
                raise

        if self._observer is not None:
            await self._observer.record(
                AuditEventType.LLM_CALL,
                source=brain_id,
                context_id=context_id,
                message=f"LLM call ({response.model})",
                data=response.metrics(),
            )
        return response

    async def _report_llm_failure(
        self, brain_id: str, context_id: str, exc: Exception
    ) -> None:
        if self._observer is None:
            return
        await report_error(
            self._observer,
            exc,
            source=brain_id,
            context_id=context_id,
            code="LLM_CALL_FAILED",
            message=f"LLM call failed: {format_exception(exc)}",
            event_type=AuditEventType.ERROR,
        )

    @staticmethod
    def _assistant_tool_message(response: LLMResponse) -> dict[str, Any]:
        """Render an assistant message echoing the requested tool calls."""
        content: list[dict[str, Any]] = []
        if response.text:
            content.append({"type": "text", "text": response.text})
        for call in response.tool_calls:
            content.append(
                {
                    "type": "tool_use",
                    "id": call.id,
                    "name": call.name,
                    "input": call.arguments,
                }
            )
        return {"role": "assistant", "content": content}

    async def _act(
        self,
        *,
        brain_id: str,
        context_id: str,
        response: LLMResponse,
        result: AgentLoopResult,
    ) -> list[dict[str, Any]]:
        """Execute each requested tool and return OBSERVE tool-result blocks."""
        tool_results: list[dict[str, Any]] = []
        for call in response.tool_calls:
            tool = self._tools.get(call.name)
            if tool is None:
                output: Any = {"error": f"unknown tool '{call.name}'"}
                is_error = True
            else:
                try:
                    output = await tool.run(call.arguments)
                    is_error = False
                except Exception as exc:
                    output = {"error": str(exc)}
                    is_error = True

            result.tool_invocations.append(
                {"tool": call.name, "arguments": call.arguments, "output": output}
            )
            if self._observer is not None:
                await self._observer.record(
                    AuditEventType.TOOL_CALL,
                    source=brain_id,
                    context_id=context_id,
                    message=f"Tool '{call.name}'",
                    data={"arguments": call.arguments, "is_error": is_error},
                )
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": str(output),
                    "is_error": is_error,
                }
            )
        return tool_results
