"""Knowledge Agent exceptions (AI layer; no Core HR AppException)."""

from app.ai.core.exceptions import AIException


class KnowledgeAgentError(AIException):
    """Base error for the Knowledge Agent orchestrator."""


class KnowledgeAgentValidationError(KnowledgeAgentError):
    """Raised when a Knowledge Agent request is invalid."""
