"""Harmless in-memory smoke tools for AI wiring tests (no DB / Core HR)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.ai.core.context import AIExecutionContext
from app.ai.tools.base import BaseTool, ToolMetadata


class GetCurrentAiContextInput(BaseModel):
    """No arguments — identity comes only from AIExecutionContext."""

    model_config = {"extra": "forbid"}


class GetCurrentAiContextOutput(BaseModel):
    model_config = {"extra": "forbid"}

    user_id: int
    roles: list[str] = Field(default_factory=list)
    employee_id: int | None = None
    candidate_id: int | None = None


class GetCurrentAiContextTool(BaseTool):
    """Read-only smoke tool that echoes authenticated AI context facts."""

    name = "get_current_ai_context"
    description = (
        "Return the authenticated caller's user_id, roles, employee_id, and "
        "candidate_id from the server-side AI execution context. "
        "Does not accept identity arguments."
    )
    metadata = ToolMetadata(
        operation="read",
        required_permissions=frozenset({"leaves:read"}),
        operates_on_current_user=True,
    )
    input_model = GetCurrentAiContextInput
    output_model = GetCurrentAiContextOutput

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, GetCurrentAiContextInput)
        return GetCurrentAiContextOutput(
            user_id=context.user_id,
            roles=sorted(context.role_names),
            employee_id=context.employee_id,
            candidate_id=context.candidate_id,
        )
