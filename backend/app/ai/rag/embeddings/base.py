"""Provider-agnostic embedding interface (separate from conversational LLM)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.ai.rag.embeddings.schemas import EmbeddingResult


class EmbeddingProvider(ABC):
    """Abstract embedding provider — one or many texts, plain Python results."""

    @abstractmethod
    def embed_text(
        self,
        text: str,
        *,
        task_type: str | None = None,
    ) -> EmbeddingResult:
        """Embed a single text string.

        ``task_type`` is provider-specific (e.g. Gemini RETRIEVAL_QUERY /
        RETRIEVAL_DOCUMENT). ``None`` uses the provider default.
        """

    @abstractmethod
    def embed_texts(
        self,
        texts: Sequence[str],
        *,
        task_type: str | None = None,
    ) -> list[EmbeddingResult]:
        """Embed multiple texts; length of results must equal length of inputs."""
