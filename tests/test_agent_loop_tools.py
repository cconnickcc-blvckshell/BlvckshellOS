"""Tests exercising the agent loop's ACT/OBSERVE (tool-calling) branch."""

from __future__ import annotations

from typing import Any

from brains._base.tools import BaseTool, ToolResult
from harness.core.agent_loop import AgentLoop
from harness.core.inference import LLMClient, LLMMessage, LLMResponse, ToolCall, _coerce_args
from harness.core.observer import Observer
from harness.core.registry import BrainRegistry
from harness.schemas.brain import BrainContext


class _CounterTool(BaseTool):
    name = "counter"
    description = "Increments a counter."
    input_schema: dict[str, Any] = {"type": "object", "properties": {"n": {"type": "integer"}}}

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def run(self, **kwargs: Any) -> ToolResult:
        self.calls.append(kwargs)
        return ToolResult(ok=True, output={"n": kwargs.get("n", 0) + 1})


class _ScriptedLLM(LLMClient):
    """Returns a tool call on the first turn, then plain text."""

    def __init__(self) -> None:
        self.model = "scripted"
        self._turn = 0

    async def complete(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        self._turn += 1
        if self._turn == 1:
            return LLMResponse(
                content="calling tool",
                tool_calls=[ToolCall(id="c1", name="counter", arguments={"n": 41})],
                model=self.model,
                usage={"total_tokens": 5, "latency_ms": 1.0},
            )
        return LLMResponse(content="done: 42", model=self.model, usage={"total_tokens": 3})


async def test_agent_loop_executes_tool_then_finishes() -> None:
    tool = _CounterTool()
    loop = AgentLoop(
        brain_id="x",
        system_prompt="sys",
        llm=_ScriptedLLM(),
        tools=[tool],
        observer=Observer(),
        registry=BrainRegistry(),
    )
    result = await loop.run(
        objective="count", context=BrainContext(context_id="c1", brain_id="x")
    )
    assert tool.calls == [{"n": 41}]
    assert result.content == "done: 42"
    assert result.iterations == 2
    assert result.tool_trace[0]["result"]["output"] == {"n": 42}
    assert result.usage["total_tokens"] == 8


def test_coerce_args_handles_json_string_and_garbage() -> None:
    assert _coerce_args('{"a": 1}') == {"a": 1}
    assert _coerce_args("not json") == {"_raw": "not json"}
    assert _coerce_args({"b": 2}) == {"b": 2}
    assert _coerce_args(12) == {}


async def test_unknown_tool_is_reported_not_crashed() -> None:
    class _OnlyUnknown(LLMClient):
        def __init__(self) -> None:
            self.model = "u"
            self._turn = 0

        async def complete(self, *, system, messages, tools=None) -> LLMResponse:  # type: ignore[no-untyped-def]
            self._turn += 1
            if self._turn == 1:
                return LLMResponse(
                    tool_calls=[ToolCall(id="c", name="ghost", arguments={})],
                    model="u",
                    usage={},
                )
            return LLMResponse(content="recovered", model="u", usage={})

    loop = AgentLoop(
        brain_id="x",
        system_prompt="sys",
        llm=_OnlyUnknown(),
        tools=[],
        observer=Observer(),
        registry=BrainRegistry(),
    )
    result = await loop.run(objective="go", context=BrainContext(context_id="c", brain_id="x"))
    assert result.content == "recovered"
