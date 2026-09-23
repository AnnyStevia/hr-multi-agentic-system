from __future__ import annotations

from app.ai.tools.base import BaseTool
from app.ai.tools.exceptions import ToolNotFoundError, ToolRegistrationError


class ToolRegistry:
    """In-memory registry of AI tools (provider-agnostic)."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        name = (tool.name or "").strip()
        if not name:
            raise ToolRegistrationError("Tool name is required")
        if name in self._tools:
            raise ToolRegistrationError(f"Tool already registered: {name}")
        self._tools[name] = tool

    def get(self, name: str) -> BaseTool:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolNotFoundError(f"Unknown tool: {name}")
        return tool

    def list_tools(self) -> list[BaseTool]:
        return [self._tools[key] for key in sorted(self._tools.keys())]
