"""Tool-layer exceptions (AI package only)."""

from app.ai.core.exceptions import AIException


class ToolRegistrationError(AIException):
    """Raised when a tool cannot be registered (e.g. duplicate name)."""


class ToolNotFoundError(AIException):
    """Raised when a requested tool name is not in the registry."""


class ToolValidationError(AIException):
    """Raised when tool arguments fail schema validation."""


class ToolAuthorizationError(AIException):
    """Raised when the caller is not allowed to execute a tool."""


class ToolExecutionError(AIException):
    """Raised when tool execution fails."""
