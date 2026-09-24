"""Embedding-layer exceptions (RAG package)."""

from app.ai.rag.exceptions import RAGException


class EmbeddingException(RAGException):
    """Base error for embedding operations."""


class EmbeddingConfigurationError(EmbeddingException):
    """Raised when embedding provider configuration is invalid."""


class EmbeddingProviderError(EmbeddingException):
    """Raised when the embedding provider/SDK call fails."""


class EmbeddingValidationError(EmbeddingException):
    """Raised when an embedding vector fails validation."""
