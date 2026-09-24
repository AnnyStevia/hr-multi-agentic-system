"""RAG embedding providers and EmbeddingService (Phase 5.4)."""

from __future__ import annotations

from app.ai.core.config import ai_settings
from app.ai.rag.config import rag_settings
from app.ai.rag.embeddings.base import EmbeddingProvider
from app.ai.rag.embeddings.exceptions import (
    EmbeddingConfigurationError,
    EmbeddingException,
    EmbeddingProviderError,
    EmbeddingValidationError,
)
from app.ai.rag.embeddings.gemini import GeminiEmbeddingProvider
from app.ai.rag.embeddings.schemas import (
    EmbedChunksResult,
    EmbeddingResult,
    EmbeddingUsage,
)
from app.ai.rag.embeddings.service import EmbeddingService
from app.ai.rag.embeddings.validation import validate_embedding_vector


def get_embedding_provider(
    *,
    api_key: str | None = None,
    model: str | None = None,
    dimensions: int | None = None,
    client=None,
) -> EmbeddingProvider:
    """Return the configured embedding provider (Gemini Embedding 2)."""
    key = ai_settings.gemini_api_key if api_key is None else api_key
    embed_model = rag_settings.rag_embedding_model if model is None else model
    dims = (
        rag_settings.rag_embedding_dimensions if dimensions is None else dimensions
    )
    return GeminiEmbeddingProvider(
        api_key=key,
        model=embed_model,
        dimensions=dims,
        client=client,
    )


__all__ = [
    "EmbedChunksResult",
    "EmbeddingConfigurationError",
    "EmbeddingException",
    "EmbeddingProvider",
    "EmbeddingProviderError",
    "EmbeddingResult",
    "EmbeddingService",
    "EmbeddingUsage",
    "EmbeddingValidationError",
    "GeminiEmbeddingProvider",
    "get_embedding_provider",
    "validate_embedding_vector",
]
