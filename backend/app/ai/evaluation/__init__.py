"""Phase 5.10 RAG evaluation — offline metrics, citation/security checks, runner."""

from app.ai.evaluation.datasets import GOLDEN_CASES, load_golden_dataset, validate_dataset
from app.ai.evaluation.schemas import (
    EvaluationCase,
    EvaluationResult,
    EvaluationSummary,
)

__all__ = [
    "GOLDEN_CASES",
    "EvaluationCase",
    "EvaluationResult",
    "EvaluationSummary",
    "load_golden_dataset",
    "validate_dataset",
]
