"""Unit tests for embedding vector validation (no Gemini / no DB)."""

import math

import pytest

from app.ai.rag.embeddings.exceptions import EmbeddingValidationError
from app.ai.rag.embeddings.validation import validate_embedding_vector


def test_validate_accepts_exact_dimensions():
    vector = [0.1, -0.2, 0.3]
    assert validate_embedding_vector(vector, expected_dimensions=3) == vector


def test_validate_rejects_missing_and_empty():
    with pytest.raises(EmbeddingValidationError, match="missing"):
        validate_embedding_vector(None, expected_dimensions=768)
    with pytest.raises(EmbeddingValidationError, match="empty"):
        validate_embedding_vector([], expected_dimensions=768)


def test_validate_rejects_dimension_mismatch():
    with pytest.raises(EmbeddingValidationError, match="dimension mismatch"):
        validate_embedding_vector([1.0, 2.0], expected_dimensions=768)


def test_validate_rejects_nan_and_inf():
    with pytest.raises(EmbeddingValidationError, match="not finite"):
        validate_embedding_vector([1.0, math.nan], expected_dimensions=2)
    with pytest.raises(EmbeddingValidationError, match="not finite"):
        validate_embedding_vector([1.0, math.inf], expected_dimensions=2)


def test_validate_rejects_non_numeric():
    with pytest.raises(EmbeddingValidationError, match="not a float"):
        validate_embedding_vector([1.0, "x"], expected_dimensions=2)  # type: ignore[list-item]
