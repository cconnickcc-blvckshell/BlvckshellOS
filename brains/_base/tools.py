"""BaseTool — the contract every brain tool implements.

Tools are the brain's hands. A tool advertises an Anthropic-shaped JSON schema
so any tool-using model can call it, and exposes a single async ``run``.
"""

from __future__ import annotations

import abc
from typing import Any

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    """The normalized output of a tool invocation.

    Attributes:
        ok: Whether the tool succeeded.
        output: Structured result data.
        error: Failure detail when ``ok`` is ``False``.
    """

    ok: bool = True
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class BaseTool(abc.ABC):
    """Abstract base class for all brain tools."""

    name: str
    description: str
    input_schema: dict[str, Any] = {"type": "object", "properties": {}}

    @abc.abstractmethod
    async def run(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with validated keyword arguments.

        Args:
            **kwargs: Arguments matching ``input_schema``.

        Returns:
            A :class:`ToolResult`.
        """

    def to_schema(self) -> dict[str, Any]:
        """Return the Anthropic-shaped tool schema for this tool.

        Returns:
            A dict with ``name``, ``description`` and ``input_schema``.
        """
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }
