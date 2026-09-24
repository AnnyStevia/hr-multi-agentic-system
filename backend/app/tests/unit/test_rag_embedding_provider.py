"""Unit tests for GeminiEmbeddingProvider (mocked google-genai client)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.ai.rag.embeddings import get_embedding_provider
from app.ai.rag.embeddings.exceptions import (
    EmbeddingConfigurationError,
    EmbeddingProviderError,
)
from app.ai.rag.embeddings.gemini import GeminiEmbeddingProvider


def _embed_response(*, values, usage=None, n: int = 1):
    embeddings = [SimpleNamespace(values=list(values)) for _ in range(n)]
    return SimpleNamespace(embeddings=embeddings, usage_metadata=usage)


def test_gemini_embedding_requires_api_key_and_model():
    with pytest.raises(EmbeddingConfigurationError, match="GEMINI_API_KEY"):
        GeminiEmbeddingProvider(api_key="", model="gemini-embedding-2", dimensions=768)
    with pytest.raises(EmbeddingConfigurationError, match="embedding model"):
        GeminiEmbeddingProvider(api_key="key", model="", dimensions=768)
    with pytest.raises(EmbeddingConfigurationError, match="dimensions"):
        GeminiEmbeddingProvider(api_key="key", model="gemini-embedding-2", dimensions=0)


def test_get_embedding_provider_returns_gemini():
    provider = get_embedding_provider(api_key="key", model="gemini-embedding-2", dimensions=768)
    assert isinstance(provider, GeminiEmbeddingProvider)
    assert provider.model == "gemini-embedding-2"
    assert provider.dimensions == 768


def test_embed_text_parses_vector_and_usage():
    client = MagicMock()
    client.models.embed_content.return_value = _embed_response(
        values=[0.1, 0.2, 0.3],
        usage=SimpleNamespace(prompt_token_count=5, total_token_count=5),
    )
    provider = GeminiEmbeddingProvider(
        api_key="key",
        model="gemini-embedding-2",
        dimensions=3,
        client=client,
    )
    result = provider.embed_text("hello")
    assert result.vector == [0.1, 0.2, 0.3]
    assert result.model == "gemini-embedding-2"
    assert result.dimensions == 3
    assert result.usage is not None
    assert result.usage.input_tokens == 5
    assert result.usage.total_tokens == 5

    kwargs = client.models.embed_content.call_args.kwargs
    assert kwargs["model"] == "gemini-embedding-2"
    assert kwargs["contents"] == "hello"
    assert kwargs["config"].output_dimensionality == 3
    assert kwargs["config"].task_type == "RETRIEVAL_DOCUMENT"


def test_embed_text_query_task_type():
    client = MagicMock()
    client.models.embed_content.return_value = _embed_response(values=[0.1, 0.2])
    provider = GeminiEmbeddingProvider(
        api_key="key",
        model="gemini-embedding-2",
        dimensions=2,
        client=client,
    )
    provider.embed_text("what is leave?", task_type="RETRIEVAL_QUERY")
    assert client.models.embed_content.call_args.kwargs["config"].task_type == (
        "RETRIEVAL_QUERY"
    )


def test_embed_texts_issues_one_call_per_text():
    client = MagicMock()
    client.models.embed_content.side_effect = [
        _embed_response(values=[1.0, 0.0]),
        _embed_response(values=[0.0, 1.0]),
    ]
    provider = GeminiEmbeddingProvider(
        api_key="key",
        model="gemini-embedding-2",
        dimensions=2,
        client=client,
    )
    results = provider.embed_texts(["a", "b"])
    assert len(results) == 2
    assert results[0].vector == [1.0, 0.0]
    assert results[1].vector == [0.0, 1.0]
    assert client.models.embed_content.call_count == 2


def test_embed_texts_empty_returns_empty():
    client = MagicMock()
    provider = GeminiEmbeddingProvider(
        api_key="key",
        model="gemini-embedding-2",
        dimensions=768,
        client=client,
    )
    assert provider.embed_texts([]) == []
    client.models.embed_content.assert_not_called()


def test_provider_api_error_wrapped():
    client = MagicMock()
    client.models.embed_content.side_effect = RuntimeError("quota")
    provider = GeminiEmbeddingProvider(
        api_key="key",
        model="gemini-embedding-2",
        dimensions=768,
        client=client,
    )
    with pytest.raises(EmbeddingProviderError, match="embedContent failed"):
        provider.embed_text("x")


def test_malformed_response_no_embeddings():
    client = MagicMock()
    client.models.embed_content.return_value = SimpleNamespace(embeddings=[])
    provider = GeminiEmbeddingProvider(
        api_key="key",
        model="gemini-embedding-2",
        dimensions=2,
        client=client,
    )
    with pytest.raises(EmbeddingProviderError, match="no embeddings"):
        provider.embed_text("x")
