"""Document Agent exceptions."""

from app.ai.core.exceptions import AIException


class DocumentsAgentError(AIException):
    """Controlled Document Agent failure."""


class DocumentsAgentValidationError(DocumentsAgentError):
    """Invalid Document Agent request."""


class DocumentsAgentAuthorizationError(DocumentsAgentError):
    """Caller is not authorized for the requested document action."""
