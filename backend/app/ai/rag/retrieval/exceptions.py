"""Retrieval-layer exceptions (RAG package)."""

from app.ai.rag.exceptions import RAGException


class RetrievalError(RAGException):
    """Base error for vector retrieval."""


class RetrievalAuthorizationError(RetrievalError):
    """Raised when the AI context is not allowed to retrieve company-library chunks."""


class RetrievalValidationError(RetrievalError):
    """Raised when a retrieval request is invalid."""
