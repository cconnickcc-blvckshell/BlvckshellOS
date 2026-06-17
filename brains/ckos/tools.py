"""Tools available to CKOS."""

from __future__ import annotations

from typing import Any

from harness.core.registry import BrainRegistry

from brains._base.tools import BaseTool, ToolResult


class ListBrainsTool(BaseTool):
    """Introspect the registry so CKOS never invents capabilities."""

    name = "list_brains"
    description = "List every registered brain and the capabilities it advertises."
    input_schema: dict[str, Any] = {"type": "object", "properties": {}}

    def __init__(self, registry: BrainRegistry) -> None:
        """Bind the tool to the live brain registry."""
        self._registry = registry

    async def run(self, **kwargs: Any) -> ToolResult:
        """Return the current map of brains to capabilities."""
        brains = await self._registry.all()
        return ToolResult(
            ok=True,
            output={
                "brains": [
                    {
                        "brain_id": b.brain_id,
                        "name": b.name,
                        "capabilities": b.capabilities,
                        "status": b.status.value,
                    }
                    for b in brains
                ]
            },
        )
