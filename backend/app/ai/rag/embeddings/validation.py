"""Validate embedding vectors before persistence."""

from __future__ import annotations

import math
from collections.abc import Sequence

from app.ai.rag.embeddings.exceptions import EmbeddingValidationError


def validate_embedding_vector(
    vector: Sequence[float] | None,
    *,
    expected_dimensions: int,
) -> list[float]:
    """Return a validated float list or raise EmbeddingValidationError.

    Does not truncate or pad — length must match ``expected_dimensions`` exactly.
    """
    if vector is None:
        raise EmbeddingValidationError("Embedding vector is missing")
    if not isinstance(vector, (list, tuple)):
        raise EmbeddingValidationError("Embedding vector must be a sequence of floats")
    if len(vector) == 0:
        raise EmbeddingValidationError("Embedding vector is empty")
    if len(vector) != expected_dimensions:
        raise EmbeddingValidationError(
            f"Embedding dimension mismatch: expected {expected_dimensions}, "
            f"got {len(vector)}"
        )

    validated: list[float] = []
    for index, value in enumerate(vector):
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise EmbeddingValidationError(
                f"Embedding value at index {index} is not a float"
            ) from exc
        if not math.isfinite(number):
            raise EmbeddingValidationError(
                f"Embedding value at index {index} is not finite"
            )
        validated.append(number)
    return validated
