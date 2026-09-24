from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    """Normalized outcome of a tool invocation."""

    model_config = {"extra": "forbid"}

    tool_name: str
    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    may_require_confirmation: bool = False


ToolOperation = Literal["read", "write"]


class ToolMetadataModel(BaseModel):
    """Pydantic view of tool metadata (optional serialization helper)."""

    model_config = {"extra": "forbid"}

    operation: ToolOperation
    required_roles: list[str] = Field(default_factory=list)
    required_permissions: list[str] = Field(default_factory=list)
    operates_on_current_user: bool = False
    may_require_confirmation: bool = False
