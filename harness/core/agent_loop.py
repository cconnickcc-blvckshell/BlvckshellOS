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

import json
import re
from dataclasses import dataclass, field
from typing import Any

from brains._base.tools import BaseTool
from judgment.profile import ModelConfig

from harness.config import Settings
from harness.core.errors import format_exception, report_error
from harness.core.llm import LLMClient, LLMResponse, OllamaClient
from harness.core.observer import Observer
from harness.logging_config import get_logger
from harness.schemas.audit import AuditEventType

logger = get_logger("agent_loop")

REPLAN_SYSTEM_PROMPT = (
    "You are reviewing your own progress on a multi-step task. Below is the "
    "transcript of what you've done so far. Decide honestly: are you "
    "converging toward the objective, or stuck — repeating the same action, "
    "going in circles, or making no real progress?\n\n"
    "Respond with ONLY a JSON object, no prose, no markdown fences:\n"
    '{"converging": true|false, "revised_approach": "<if not converging, a '
    'concise restated strategy to adopt instead; otherwise an empty string>"}'
)

_REPLAN_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_replan_json(text: str) -> dict[str, Any] | None:
    """Best-effort extraction of a JSON object from a critique response."""
    match = _REPLAN_JSON_RE.search(text)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


@dataclass(slots=True)
class AgentLoopResult:
    """The outcome of running the agent loop for one task."""

    final_text: str = ""
    iterations: int = 0
    tool_invocations: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    transcript: list[dict[str, Any]] = field(default_factory=list)
    replans: list[dict[str, Any]] = field(default_factory=list)


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
        replan_checkpoint: int = 3,
        max_replans: int = 2,
    ) -> None:
        self._llm = llm
        self._tools = {tool.name: tool for tool in (tools or [])}
        self._observer = observer
        self._max_iterations = max_iterations
        self._model_config = model_config
        self._settings = settings
        self._replan_checkpoint = replan_checkpoint
        self._max_replans = max_replans

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
        active_system_prompt = system_prompt
        last_tool_signature: tuple[tuple[str, str], ...] | None = None
        replans_used = 0

        for _ in range(self._max_iterations):
            result.iterations += 1
            response = await self._think(
                brain_id=brain_id,
                context_id=context_id,
                system_prompt=active_system_prompt,
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

            tool_signature = tuple(
                sorted(
                    (call.name, json.dumps(call.arguments, sort_keys=True, default=str))
                    for call in response.tool_calls
                )
            )
            stalled = tool_signature == last_tool_signature
            last_tool_signature = tool_signature

            messages.append(self._assistant_tool_message(response))
            tool_results = await self._act(
                brain_id=brain_id, context_id=context_id, response=response, result=result
            )
            messages.append({"role": "user", "content": tool_results})

            at_checkpoint = result.iterations == self._replan_checkpoint
            if replans_used < self._max_replans and (stalled or at_checkpoint):
                reason = "stalled" if stalled else "checkpoint"
                revised_prompt, replan_response = await self._replan(
                    brain_id=brain_id,
                    context_id=context_id,
                    system_prompt=active_system_prompt,
                    messages=messages,
                    reason=reason,
                )
                replans_used += 1
                if replan_response is not None:
                    total_in += replan_response.input_tokens
                    total_out += replan_response.output_tokens
                    total_cost += replan_response.cost_usd
                    total_latency += replan_response.latency_ms
                if revised_prompt is not None:
                    active_system_prompt = revised_prompt
                    result.replans.append({"reason": reason, "iteration": result.iterations})
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
            "replans": replans_used,
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

    async def _replan(
        self,
        *,
        brain_id: str,
        context_id: str,
        system_prompt: str,
        messages: list[dict[str, Any]],
        reason: str,
    ) -> tuple[str | None, LLMResponse | None]:
        """Ask the model to critique its own progress and revise the system prompt.

        Returns ``(revised_system_prompt, response)``. ``revised_system_prompt``
        is ``None`` when the critique judges the loop to be converging fine, or
        when the critique call itself fails — in either case the loop continues
        unchanged. ``response`` carries usage metrics for the critique call
        (``None`` only on failure) so callers can fold its cost into totals.
        """
        transcript = json.dumps(messages[-6:], default=str)[:4000]
        try:
            response = await self._llm.complete(
                system=REPLAN_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": f"TRANSCRIPT:\n{transcript}"}],
                max_tokens=400,
            )
        except Exception as exc:
            logger.warning("agent_loop_replan_failed", brain_id=brain_id, error=str(exc))
            return None, None

        parsed = _extract_replan_json(response.text)
        if not parsed or parsed.get("converging", True):
            return None, response

        revised = str(parsed.get("revised_approach", "")).strip()
        if not revised:
            return None, response

        if self._observer is not None:
            await self._observer.record(
                AuditEventType.AGENT_LOOP_REPLANNED,
                source=brain_id,
                context_id=context_id,
                message=revised[:160],
                data={"reason": reason},
            )
        return f"{system_prompt}\n\nSELF-CRITIQUE — REVISED APPROACH:\n{revised}", response

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
