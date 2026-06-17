"""Tests for the think/act/observe agent loop."""

from __future__ import annotations

from typing import Any

from brains._base.tools import FunctionTool

from harness.core.agent_loop import AgentLoop
from harness.core.llm import FakeLLMClient, LLMResponse, ToolCall


async def test_single_turn_completes_without_tools() -> None:
    llm = FakeLLMClient()
    loop = AgentLoop(llm=llm, tools=[])
    result = await loop.run(
        brain_id="venture",
        context_id="c1",
        system_prompt="sys",
        user_prompt="do the thing",
    )
    assert result.iterations == 1
    assert "do the thing" in result.final_text
    assert result.metrics["tool_calls"] == 0


async def test_tool_call_is_executed_then_loop_finishes() -> None:
    calls: list[dict[str, Any]] = []

    async def echo(arguments: dict[str, Any]) -> dict[str, Any]:
        calls.append(arguments)
        return {"echoed": arguments}

    tool = FunctionTool(
        name="echo",
        description="echo args",
        input_schema={"type": "object", "properties": {}},
        func=echo,
    )
    scripted = [
        LLMResponse(
            tool_calls=[ToolCall(id="t1", name="echo", arguments={"v": 1})],
            stop_reason="tool_use",
        ),
        LLMResponse(text="done", stop_reason="end_turn"),
    ]
    loop = AgentLoop(llm=FakeLLMClient(scripted=scripted), tools=[tool])
    result = await loop.run(
        brain_id="venture",
        context_id="c1",
        system_prompt="sys",
        user_prompt="use the tool",
    )
    assert calls == [{"v": 1}]
    assert result.iterations == 2
    assert result.final_text == "done"
    assert result.tool_invocations[0]["tool"] == "echo"


async def test_unknown_tool_is_reported_not_raised() -> None:
    scripted = [
        LLMResponse(
            tool_calls=[ToolCall(id="t1", name="ghost", arguments={})],
            stop_reason="tool_use",
        ),
        LLMResponse(text="recovered", stop_reason="end_turn"),
    ]
    loop = AgentLoop(llm=FakeLLMClient(scripted=scripted), tools=[])
    result = await loop.run(
        brain_id="venture",
        context_id="c1",
        system_prompt="sys",
        user_prompt="use a missing tool",
    )
    assert result.final_text == "recovered"
    assert "error" in result.tool_invocations[0]["output"]
