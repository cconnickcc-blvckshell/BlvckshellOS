"""The agent loop — the core THINK / ACT / OBSERVE / ITERATE cycle.

Every brain runs work through this loop. It is deliberately small and explicit:
call the model, run any requested tools, feed observations back, repeat until the
model stops requesting tools or the iteration cap is hit. Every model call and
tool call is audited.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from brains._base.tools import BaseTool, ToolResult

from harness.config import settings
from harness.core.inference import LLMClient, LLMMessage
from harness.core.logging import get_logger
from harness.core.observer import Observer
from harness.schemas.brain import BrainContext, BrainStatus
from harness.schemas.event import EventType

if TYPE_CHECKING:  # pragma: no cover - typing only
    from harness.core.registry import BrainRegistry

logger = get_logger(__name__)


class AgentLoopResult:
    """The outcome of running the agent loop.

    Attributes:
        content: The final assistant text.
        tool_trace: Ordered record of tool invocations and their results.
        usage: Aggregate token/latency accounting across all model calls.
        iterations: Number of model calls made.
    """

    def __init__(
        self,
        *,
        content: str,
        tool_trace: list[dict[str, Any]],
        usage: dict[str, float],
        iterations: int,
    ) -> None:
        """Store the loop outcome fields."""
        self.content = content
        self.tool_trace = tool_trace
        self.usage = usage
        self.iterations = iterations

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the result."""
        return {
            "content": self.content,
            "tool_trace": self.tool_trace,
            "usage": self.usage,
            "iterations": self.iterations,
        }


class AgentLoop:
    """Reusable THINK/ACT/OBSERVE engine bound to one brain's resources."""

    def __init__(
        self,
        *,
        brain_id: str,
        system_prompt: str,
        llm: LLMClient,
        tools: list[BaseTool],
        observer: Observer,
        registry: BrainRegistry,
    ) -> None:
        """Bind the loop to a brain's model, tools and runtime hooks."""
        self._brain_id = brain_id
        self._system_prompt = system_prompt
        self._llm = llm
        self._tools = {tool.name: tool for tool in tools}
        self._tool_schemas = [tool.to_schema() for tool in tools] or None
        self._observer = observer
        self._registry = registry

    async def run(
        self,
        *,
        objective: str,
        context: BrainContext,
        max_iterations: int | None = None,
    ) -> AgentLoopResult:
        """Execute the loop until resolution or the iteration cap.

        Args:
            objective: The natural-language objective.
            context: The loaded :class:`BrainContext`.
            max_iterations: Optional override for the iteration cap.

        Returns:
            An :class:`AgentLoopResult`.
        """
        limit = max_iterations or settings.max_agent_iterations
        messages: list[LLMMessage] = [
            LLMMessage(
                role="user",
                content=f"OBJECTIVE:\n{objective}\n\nCONTEXT:\n{self._render_context(context)}",
            )
        ]
        tool_trace: list[dict[str, Any]] = []
        usage_total: dict[str, float] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "latency_ms": 0.0,
        }
        final_content = ""
        iterations = 0

        for _ in range(limit):
            iterations += 1
            response = await self._llm.complete(
                system=self._system_prompt, messages=messages, tools=self._tool_schemas
            )
            self._accumulate_usage(usage_total, response.usage)
            await self._observer.record(
                EventType.LLM_CALL,
                source=self._brain_id,
                context_id=context.context_id,
                message=f"llm call ({response.model})",
                data=response.usage,
            )
            if response.content:
                final_content = response.content

            if not response.tool_calls:
                break

            await self._registry.set_status(self._brain_id, BrainStatus.EXECUTING)
            observations: list[str] = []
            for call in response.tool_calls:
                tool = self._tools.get(call.name)
                if tool is None:
                    observations.append(f"[{call.name}] unknown tool")
                    continue
                result = await self._invoke_tool(tool, call.arguments, context.context_id)
                tool_trace.append(
                    {
                        "tool": call.name,
                        "arguments": call.arguments,
                        "result": result.model_dump(),
                    }
                )
                observations.append(f"[{call.name}] ok={result.ok} output={result.output}")
            messages.append(
                LLMMessage(role="assistant", content=response.content or "(requesting tools)")
            )
            messages.append(
                LLMMessage(role="user", content="TOOL RESULTS:\n" + "\n".join(observations))
            )
            await self._registry.set_status(self._brain_id, BrainStatus.THINKING)

        return AgentLoopResult(
            content=final_content,
            tool_trace=tool_trace,
            usage=usage_total,
            iterations=iterations,
        )

    async def _invoke_tool(
        self, tool: BaseTool, arguments: dict[str, Any], context_id: str
    ) -> ToolResult:
        """Run a tool with auditing and error isolation."""
        try:
            result = await tool.run(**arguments)
        except Exception as exc:  # noqa: BLE001 - tool failures are observations
            result = ToolResult(ok=False, error=str(exc))
        await self._observer.record(
            EventType.TOOL_CALL,
            source=self._brain_id,
            context_id=context_id,
            message=f"tool {tool.name}",
            data={"arguments": arguments, "ok": result.ok, "error": result.error},
        )
        return result

    @staticmethod
    def _render_context(context: BrainContext) -> str:
        """Render a compact textual view of context for the model."""
        beliefs = [d.get("belief") for d in context.doctrine][:5]
        return (
            f"Working memory: {context.working}\n"
            f"Active doctrine ({len(context.doctrine)}): {beliefs}\n"
            f"Recent judgments: {len(context.recent_judgments)}\n"
            f"Recent episodes: {len(context.episodic)}"
        )

    @staticmethod
    def _accumulate_usage(total: dict[str, float], usage: dict[str, Any]) -> None:
        """Fold a single call's usage into the running aggregate."""
        for key in ("prompt_tokens", "completion_tokens", "total_tokens", "latency_ms"):
            total[key] = total.get(key, 0) + float(usage.get(key, 0) or 0)
