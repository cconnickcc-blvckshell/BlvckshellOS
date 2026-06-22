"""Tests for the think/act/observe agent loop."""

from __future__ import annotations

from typing import Any

from brains._base.tools import FunctionTool

from harness.core.agent_loop import AgentLoop
from harness.core.llm import FakeLLMClient, LLMResponse, ToolCall
from harness.core.observer import InMemoryAuditStore, Observer
from harness.schemas.audit import AuditEventType


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


def _search_tool() -> FunctionTool:
    async def search(arguments: dict[str, Any]) -> dict[str, Any]:
        return {"results": []}

    return FunctionTool(
        name="search",
        description="search for something",
        input_schema={"type": "object", "properties": {}},
        func=search,
    )


async def test_repeated_identical_tool_call_triggers_replan() -> None:
    same_call = ToolCall(id="t", name="search", arguments={"q": "x"})
    scripted = [
        LLMResponse(tool_calls=[same_call], stop_reason="tool_use"),
        LLMResponse(tool_calls=[same_call], stop_reason="tool_use"),
        LLMResponse(text='{"converging": false, "revised_approach": "switch strategy"}'),
        LLMResponse(text="done"),
    ]
    llm = FakeLLMClient(scripted=scripted)
    observer = Observer(InMemoryAuditStore())
    loop = AgentLoop(llm=llm, tools=[_search_tool()], observer=observer)

    result = await loop.run(
        brain_id="venture",
        context_id="c1",
        system_prompt="sys",
        user_prompt="find it",
    )

    assert result.iterations == 3
    assert result.final_text == "done"
    assert result.replans == [{"reason": "stalled", "iteration": 2}]
    assert llm.calls[0]["system"] == "sys"
    assert llm.calls[2]["system"].startswith("You are reviewing your own progress")
    assert llm.calls[3]["system"] == "sys\n\nSELF-CRITIQUE — REVISED APPROACH:\nswitch strategy"

    events = await observer.list_recent()
    assert any(e.event_type == AuditEventType.AGENT_LOOP_REPLANNED for e in events)


async def test_replan_at_checkpoint_with_no_revision_when_converging() -> None:
    scripted = [
        LLMResponse(
            tool_calls=[ToolCall(id="t1", name="search", arguments={"q": "a"})],
            stop_reason="tool_use",
        ),
        LLMResponse(
            tool_calls=[ToolCall(id="t2", name="search", arguments={"q": "b"})],
            stop_reason="tool_use",
        ),
        LLMResponse(text='{"converging": true, "revised_approach": ""}'),
        LLMResponse(text="done"),
    ]
    llm = FakeLLMClient(scripted=scripted)
    observer = Observer(InMemoryAuditStore())
    loop = AgentLoop(
        llm=llm,
        tools=[_search_tool()],
        observer=observer,
        replan_checkpoint=2,
        max_replans=2,
    )

    result = await loop.run(
        brain_id="venture",
        context_id="c1",
        system_prompt="sys",
        user_prompt="find it",
    )

    assert result.iterations == 3
    assert result.metrics["replans"] == 1
    assert result.replans == []
    assert llm.calls[3]["system"] == "sys"

    events = await observer.list_recent()
    assert not any(e.event_type == AuditEventType.AGENT_LOOP_REPLANNED for e in events)


async def test_max_replans_caps_critique_calls() -> None:
    same_call = ToolCall(id="t", name="search", arguments={"q": "x"})
    scripted = [
        LLMResponse(tool_calls=[same_call], stop_reason="tool_use"),
        LLMResponse(tool_calls=[same_call], stop_reason="tool_use"),
        LLMResponse(text='{"converging": true, "revised_approach": ""}'),
        LLMResponse(tool_calls=[same_call], stop_reason="tool_use"),
        LLMResponse(tool_calls=[same_call], stop_reason="tool_use"),
    ]
    llm = FakeLLMClient(scripted=scripted)
    loop = AgentLoop(
        llm=llm,
        tools=[_search_tool()],
        max_iterations=4,
        replan_checkpoint=100,
        max_replans=1,
    )

    result = await loop.run(
        brain_id="venture",
        context_id="c1",
        system_prompt="sys",
        user_prompt="find it",
    )

    assert result.iterations == 4
    assert result.metrics["replans"] == 1
    assert len(llm.calls) == 5
    assert result.final_text == "Reached iteration limit without completion."
