"""Recruitment AI exceptions (AI layer; no Core HR AppException)."""

from app.ai.core.exceptions import AIException


class RecruitmentExtractionError(AIException):
    """Base error for CV extraction."""


class RecruitmentExtractionValidationError(RecruitmentExtractionError):
    """Raised when CV input or LLM structured output is invalid."""


class RecruitmentExtractionUnsupportedError(RecruitmentExtractionError):
    """Raised when the CV file type cannot be parsed."""


class RecruitmentFitError(AIException):
    """Base error for candidate/job fit analysis."""


class RecruitmentFitValidationError(RecruitmentFitError):
    """Raised when fit input or LLM structured output is invalid."""
