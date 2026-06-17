"""The tool contract every brain capability is built from.

A :class:`BaseTool` wraps a single capability the model can invoke during the
agent loop. Tools declare a JSON-schema for their inputs and implement an async
``run``. Keep tools small, explicit, and side-effect-honest.
"""

from __future__ import annotations

import abc
from typing import Any


class BaseTool(abc.ABC):
    """Abstract executable tool exposed to a brain's LLM.

    Subclasses set :attr:`name`, :attr:`description`, and :attr:`input_schema`,
    and implement :meth:`run`.
    """

    name: str = "tool"
    description: str = ""
    input_schema: dict[str, Any] = {"type": "object", "properties": {}}

    @abc.abstractmethod
    async def run(self, arguments: dict[str, Any]) -> Any:
        """Execute the tool.

        Args:
            arguments: Arguments validated loosely against :attr:`input_schema`.

        Returns:
            A JSON-serializable result handed back to the model.
        """

    def to_schema(self) -> dict[str, Any]:
        """Return the Anthropic-compatible tool schema for this tool."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


class FunctionTool(BaseTool):
    """Adapter that turns an async function into a :class:`BaseTool`."""

    def __init__(
        self,
        *,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        func: Any,
    ) -> None:
        """Create a function-backed tool.

        Args:
            name: The tool name.
            description: What the tool does.
            input_schema: JSON schema for the tool inputs.
            func: An async callable ``(arguments: dict) -> Any``.
        """
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self._func = func

    async def run(self, arguments: dict[str, Any]) -> Any:
        """Invoke the wrapped async function with the given arguments."""
        return await self._func(arguments)
