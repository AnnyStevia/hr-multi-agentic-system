from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError

from app.ai.core.context import AIExecutionContext
from app.ai.tools.authorization import authorize_tool
from app.ai.tools.exceptions import ToolExecutionError, ToolValidationError
from app.ai.tools.registry import ToolRegistry
from app.ai.tools.schemas import ToolResult


class ToolExecutor:
    """Resolves, validates, authorizes, and runs registered tools under an AI context."""

    def __init__(self, registry: ToolRegistry):
        self._registry = registry

    def execute(
        self,
        context: AIExecutionContext | None,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        # 1. Resolve tool
        tool = self._registry.get(tool_name)

        # 2. Validate arguments
        try:
            args = tool.input_model.model_validate(arguments)
        except ValidationError as exc:
            raise ToolValidationError(
                f"Invalid arguments for tool '{tool_name}': {exc.error_count()} validation error(s)"
            ) from exc

        # 3. Authorize (raises ToolAuthorizationError on deny)
        authorize_tool(tool, context, args)

        # 4. Execute tool
        try:
            output = tool.execute(context, args)
        except ToolExecutionError:
            raise
        except Exception as exc:
            raise ToolExecutionError(
                f"Tool '{tool_name}' failed: {exc}"
            ) from exc

        # 5. Normalize result
        if not isinstance(output, tool.output_model):
            try:
                output = tool.output_model.model_validate(
                    output.model_dump() if isinstance(output, BaseModel) else output
                )
            except (ValidationError, AttributeError, TypeError) as exc:
                raise ToolExecutionError(
                    f"Tool '{tool_name}' returned an invalid output payload"
                ) from exc

        return ToolResult(
            tool_name=tool.name,
            success=True,
            data=output.model_dump(mode="json"),
            error=None,
            may_require_confirmation=tool.metadata.may_require_confirmation,
        )
