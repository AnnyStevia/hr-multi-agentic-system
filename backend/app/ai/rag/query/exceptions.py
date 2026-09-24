"""RAG query pipeline exceptions."""

from app.ai.rag.exceptions import RAGException


class RAGQueryError(RAGException):
    """Base error for the RAG query pipeline."""


class RAGQueryValidationError(RAGQueryError):
    """Raised when a RAG query request is invalid."""
