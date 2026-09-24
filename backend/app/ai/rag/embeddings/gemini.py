"""Gemini Embedding 2 provider (google-genai SDK).

gemini-embedding-2 aggregates multi-string inputs into one vector, so this
provider issues one synchronous embed_content call per text.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from google import genai
from google.genai import types

from app.ai.rag.embeddings.base import EmbeddingProvider
from app.ai.rag.embeddings.exceptions import (
    EmbeddingConfigurationError,
    EmbeddingProviderError,
)
from app.ai.rag.embeddings.schemas import EmbeddingResult, EmbeddingUsage

DEFAULT_DOCUMENT_TASK_TYPE = "RETRIEVAL_DOCUMENT"
DEFAULT_QUERY_TASK_TYPE = "RETRIEVAL_QUERY"


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Gemini embedContent adapter behind EmbeddingProvider."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        dimensions: int,
        client: Any | None = None,
    ) -> None:
        if not api_key or not api_key.strip():
            raise EmbeddingConfigurationError("GEMINI_API_KEY is required")
        if not model or not model.strip():
            raise EmbeddingConfigurationError("RAG embedding model is required")
        if dimensions < 1:
            raise EmbeddingConfigurationError("RAG embedding dimensions must be >= 1")
        self._model = model.strip()
        self._dimensions = dimensions
        self._client = client if client is not None else genai.Client(api_key=api_key.strip())

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed_text(
        self,
        text: str,
        *,
        task_type: str | None = None,
    ) -> EmbeddingResult:
        results = self.embed_texts([text], task_type=task_type)
        return results[0]

    def embed_texts(
        self,
        texts: Sequence[str],
        *,
        task_type: str | None = None,
    ) -> list[EmbeddingResult]:
        if not texts:
            return []
        effective = (task_type or DEFAULT_DOCUMENT_TASK_TYPE).strip() or DEFAULT_DOCUMENT_TASK_TYPE
        results: list[EmbeddingResult] = []
        for text in texts:
            results.append(self._embed_one(text, task_type=effective))
        return results

    def _embed_one(self, text: str, *, task_type: str) -> EmbeddingResult:
        try:
            response = self._client.models.embed_content(
                model=self._model,
                contents=text,
                config=types.EmbedContentConfig(
                    output_dimensionality=self._dimensions,
                    task_type=task_type,
                ),
            )
        except EmbeddingProviderError:
            raise
        except Exception as exc:
            raise EmbeddingProviderError(
                f"Gemini embedContent failed: {exc}"
            ) from exc

        vector = _extract_vector(response)
        return EmbeddingResult(
            vector=vector,
            model=self._model,
            dimensions=self._dimensions,
            usage=_extract_usage(response),
        )


def _extract_vector(response: Any) -> list[float]:
    embeddings = getattr(response, "embeddings", None) or []
    if not embeddings:
        raise EmbeddingProviderError("Gemini embedContent returned no embeddings")
    values = getattr(embeddings[0], "values", None)
    if values is None:
        raise EmbeddingProviderError("Gemini embedding values are missing")
    try:
        return [float(v) for v in values]
    except (TypeError, ValueError) as exc:
        raise EmbeddingProviderError(
            "Gemini embedding values must be numeric"
        ) from exc


def _extract_usage(response: Any) -> EmbeddingUsage | None:
    meta = getattr(response, "usage_metadata", None)
    if meta is None:
        return None
    input_tokens = _as_optional_int(
        getattr(meta, "prompt_token_count", None)
        if getattr(meta, "prompt_token_count", None) is not None
        else getattr(meta, "input_token_count", None)
    )
    total_tokens = _as_optional_int(getattr(meta, "total_token_count", None))
    if input_tokens is None and total_tokens is None:
        return None
    return EmbeddingUsage(input_tokens=input_tokens, total_tokens=total_tokens)


def _as_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
