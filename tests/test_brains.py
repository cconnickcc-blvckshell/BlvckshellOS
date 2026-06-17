"""Tests for brain behavior, the agent loop, and tools."""

from __future__ import annotations

from typing import Any

from brains._base.tools import BaseTool, ToolResult
from brains._base.worker import LLMWorkerBrain
from harness.core.runtime import HarnessRuntime
from harness.schemas.brain import BrainContext
from harness.schemas.message import HarnessMessage, MessageType
from harness.schemas.result import ResultStatus
from harness.schemas.task import TaskPayload


class _EchoTool(BaseTool):
    name = "echo"
    description = "Echo a value back."
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"value": {"type": "string"}},
    }

    async def run(self, **kwargs: Any) -> ToolResult:
        return ToolResult(ok=True, output={"echo": kwargs.get("value")})


class _CrashTool(BaseTool):
    name = "crash"
    description = "Always raises."
    input_schema: dict[str, Any] = {"type": "object", "properties": {}}

    async def run(self, **kwargs: Any) -> ToolResult:
        raise RuntimeError("tool exploded")


class _WorkerWithTools(LLMWorkerBrain):
    brain_id = "worker_x"
    name = "Worker X"
    description = "test worker"
    capabilities = ["do_x"]


async def test_worker_handle_task_returns_success(runtime: HarnessRuntime) -> None:
    brain = _WorkerWithTools(runtime)
    await brain.start()
    task = HarnessMessage(
        source="harness",
        destination="worker_x",
        message_type=MessageType.TASK,
        payload=TaskPayload(task_id="t1", capability="do_x", objective="do the thing").model_dump(
            mode="json"
        ),
    )
    result_msg = await brain.handle_task(task)
    assert result_msg.message_type == MessageType.RESULT
    assert result_msg.payload["status"] == ResultStatus.SUCCESS.value
    # A judgment must have been logged for the work.
    assert result_msg.payload["judgment_ids"]
    await brain.stop()


async def test_agent_loop_runs_tools(runtime: HarnessRuntime) -> None:
    brain = _WorkerWithTools(runtime, tools=[_EchoTool()])
    context = BrainContext(context_id="c1", brain_id="worker_x")
    # The stub LLM never calls tools, so the loop simply produces content.
    result = await brain.think(objective="hello", context=context)
    assert result.content
    assert result.iterations >= 1


async def test_crashing_tool_is_isolated(runtime: HarnessRuntime) -> None:
    # Even a crashing tool must not surface as an exception in the loop.
    from harness.core.agent_loop import AgentLoop

    loop = AgentLoop(
        brain_id="worker_x",
        system_prompt="x",
        llm=runtime.llm_factory("stub-1"),
        tools=[_CrashTool()],
        observer=runtime.observer,
        registry=runtime.registry,
    )
    context = BrainContext(context_id="c1", brain_id="worker_x")
    result = await loop.run(objective="go", context=context)
    assert result.content is not None


async def test_failing_brain_returns_failure_not_crash(runtime: HarnessRuntime) -> None:
    class _BrokenBrain(LLMWorkerBrain):
        brain_id = "broken"
        name = "Broken"
        description = "always fails"
        capabilities = ["break"]

        async def handle_task(self, task: HarnessMessage) -> HarnessMessage:
            raise RuntimeError("kaboom")

    brain = _BrokenBrain(runtime)
    await brain.start()
    received: list[HarnessMessage] = []

    async def collector(msg: HarnessMessage) -> None:
        received.append(msg)

    await runtime.bus.subscribe("harness", collector)
    await runtime.bus.publish(
        HarnessMessage(
            source="harness",
            destination="broken",
            message_type=MessageType.TASK,
            payload={"task_id": "t1", "objective": "x"},
        )
    )
    assert received
    assert received[-1].payload["status"] == ResultStatus.FAILED.value
    await brain.stop()
