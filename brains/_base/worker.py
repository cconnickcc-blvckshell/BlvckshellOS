"""LLMWorkerBrain — a ready-made base for specialist worker brains.

Most brains follow the same shape: receive a task, load context, run the agent
loop, log a judgment, return a result. This class implements that shape so a new
worker brain is just metadata plus (optionally) tools and a belief statement.
"""

from __future__ import annotations

from harness.core.logging import get_logger
from harness.schemas.brain import BrainContext
from harness.schemas.judgment import JudgmentEntry
from harness.schemas.message import HarnessMessage, MessageType
from harness.schemas.result import ResultPayload, ResultStatus
from harness.schemas.task import TaskPayload

from brains._base.brain import BaseBrain

logger = get_logger(__name__)


class LLMWorkerBrain(BaseBrain):
    """A specialist brain that resolves a task with a single agent loop."""

    default_confidence: float = 0.6

    async def get_context(self, context_id: str) -> BrainContext:
        """Load context from shared memory (default implementation)."""
        return await self.default_context(context_id)

    async def log_judgment(self, entry: JudgmentEntry) -> None:
        """Record a judgment to the ledger (default implementation)."""
        await self.default_log_judgment(entry)

    def belief_for(self, task: TaskPayload, loop_content: str) -> str:
        """Return the belief this brain wants to log for a finished task.

        Override to express domain-specific judgments. The default records that
        the brain produced output for the objective.

        Args:
            task: The task that was handled.
            loop_content: The agent loop's final text.

        Returns:
            A belief statement for the Judgment Ledger.
        """
        return f"{self.name} produced an assessment for: {task.objective[:160]}"

    async def handle_task(self, task: HarnessMessage) -> HarnessMessage:
        """Run the standard receive→context→think→judge→result flow.

        Args:
            task: The incoming ``TASK`` message.

        Returns:
            A ``RESULT`` message addressed back to the sender.
        """
        payload = TaskPayload.model_validate(task.payload)
        context = await self.get_context(task.context_id)
        loop = await self.think(objective=payload.objective, context=context)

        judgment = JudgmentEntry(
            brain_id=self.brain_id,
            context_id=task.context_id,
            belief=self.belief_for(payload, loop.content),
            confidence=self.default_confidence,
            evidence=[f"agent_loop_iterations={loop.iterations}"]
            + [t["tool"] for t in loop.tool_trace],
            assumptions=["operator intent as stated", "registered capabilities are accurate"],
        )
        await self.log_judgment(judgment)

        result = ResultPayload(
            task_id=payload.task_id,
            brain_id=self.brain_id,
            status=ResultStatus.SUCCESS,
            summary=loop.content,
            output={"objective": payload.objective, "tool_trace": loop.tool_trace},
            judgment_ids=[judgment.id],
            usage=loop.usage,
        )
        return task.reply(
            source=self.brain_id,
            message_type=MessageType.RESULT,
            payload=result.model_dump(mode="json"),
        )
