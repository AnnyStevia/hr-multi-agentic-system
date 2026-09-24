"""Authorize AI tools against AIExecutionContext using Core HR RBAC semantics."""

from __future__ import annotations

from pydantic import BaseModel

from app.ai.core.context import AIExecutionContext
from app.ai.tools.base import BaseTool
from app.ai.tools.exceptions import ToolAuthorizationError

_GENERIC_DENY = "Not authorized to execute this tool"

# Identity fields that must match AIExecutionContext when operates_on_current_user.
_IDENTITY_FIELDS = ("user_id", "employee_id", "candidate_id")


def authorize_tool(
    tool: BaseTool,
    context: AIExecutionContext | None,
    args: BaseModel,
) -> None:
    """Enforce tool metadata against authenticated context.

    Mirrors Core HR dependency semantics:
    - required_roles: OR (at least one)
    - required_permissions: AND (all required)
    - operates_on_current_user: reject foreign identity in args

    Raises ToolAuthorizationError with a generic message (no sensitive detail).
    """
    if context is None:
        raise ToolAuthorizationError(_GENERIC_DENY)

    metadata = tool.metadata

    if metadata.required_roles and not context.has_any_role(*metadata.required_roles):
        raise ToolAuthorizationError(_GENERIC_DENY)

    if metadata.required_permissions:
        missing = metadata.required_permissions - context.permission_names
        if missing:
            raise ToolAuthorizationError(_GENERIC_DENY)

    if metadata.operates_on_current_user:
        _enforce_current_user_identity(context, args)


def _enforce_current_user_identity(
    context: AIExecutionContext,
    args: BaseModel,
) -> None:
    for field_name in _IDENTITY_FIELDS:
        if field_name not in type(args).model_fields:
            continue
        claimed = getattr(args, field_name, None)
        if claimed is None:
            continue
        expected = getattr(context, field_name)
        if claimed != expected:
            raise ToolAuthorizationError(_GENERIC_DENY)
