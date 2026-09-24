"""RAG grounded generation exceptions."""

from app.ai.rag.exceptions import RAGException


class RAGGenerationError(RAGException):
    """Base error for grounded answer generation."""


class RAGGenerationValidationError(RAGGenerationError):
    """Raised when generation input or model output is invalid."""
