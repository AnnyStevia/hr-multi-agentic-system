from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel, ValidationError

from app.ai.confirmation import create_confirmation_token
from app.ai.core.context import AIExecutionContext
from app.ai.tools.authorization import authorize_tool
from app.ai.tools.exceptions import ToolExecutionError, ToolValidationError
from app.ai.tools.registry import ToolRegistry
from app.ai.tools.schemas import ToolResult

PreviewBuilder = Callable[[str, dict[str, Any], AIExecutionContext | None], str]


def _default_preview(tool_name: str, arguments: dict[str, Any], _context) -> str:
    parts = [f"Proposed action: {tool_name}"]
    for key in sorted(arguments.keys()):
        parts.append(f"- {key}: {arguments[key]}")
    parts.append("No changes have been applied yet. Confirm to proceed.")
    return "\n".join(parts)


def _infer_target(tool_name: str, arguments: dict[str, Any]) -> tuple[str | None, int | None]:
    if "interview_id" in arguments and arguments["interview_id"] is not None:
        return "interview", int(arguments["interview_id"])
    if "application_id" in arguments and arguments["application_id"] is not None:
        return "application", int(arguments["application_id"])
    if "employee_id" in arguments and arguments["employee_id"] is not None:
        return "employee", int(arguments["employee_id"])
    return None, None


class ToolExecutor:
    """Resolves, validates, authorizes, and runs registered tools under an AI context."""

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        preview_builder: PreviewBuilder | None = None,
    ):
        self._registry = registry
        self._preview_builder = preview_builder or _default_preview

    def execute(
        self,
        context: AIExecutionContext | None,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        execute_writes: bool = False,
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

        # Canonical JSON-serializable args (stable for token binding)
        canonical_args = args.model_dump(mode="json")

        # 3. Authorize (raises ToolAuthorizationError on deny)
        authorize_tool(tool, context, args)

        # 4. Gate writes that require confirmation unless this is a verified confirm path
        if tool.metadata.may_require_confirmation and not execute_writes:
            if context is None or context.user_id is None:
                raise ToolExecutionError("Authenticated user required for write confirmation")
            summary = self._preview_builder(tool.name, canonical_args, context)
            target_type, target_id = _infer_target(tool.name, canonical_args)
            token, payload = create_confirmation_token(
                user_id=context.user_id,
                tool_name=tool.name,
                arguments=canonical_args,
                summary=summary,
                target_type=target_type,
                target_id=target_id,
            )
            return ToolResult(
                tool_name=tool.name,
                success=True,
                data={
                    "status": "pending_confirmation",
                    "tool_name": tool.name,
                    "summary": summary,
                    "arguments": canonical_args,
                    "message": (
                        "This write action requires explicit confirmation. "
                        "No database changes have been made yet."
                    ),
                },
                error=None,
                may_require_confirmation=True,
                confirmation_token=token,
                confirmation_summary=summary,
                confirmation_expires_at=payload.exp,
            )

        # 5. Execute tool
        try:
            output = tool.execute(context, args)
        except ToolExecutionError:
            raise
        except Exception as exc:
            raise ToolExecutionError(
                f"Tool '{tool_name}' failed: {exc}"
            ) from exc

        # 6. Normalize result
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
