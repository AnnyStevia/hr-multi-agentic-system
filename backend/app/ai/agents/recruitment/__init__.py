"""Recruitment AI — CV extraction (6.1) and fit analysis (6.2)."""

from app.ai.agents.recruitment.exceptions import (
    RecruitmentExtractionError,
    RecruitmentExtractionUnsupportedError,
    RecruitmentExtractionValidationError,
    RecruitmentFitError,
    RecruitmentFitValidationError,
)
from app.ai.agents.recruitment.fit_service import FitAnalysisService
from app.ai.agents.recruitment.schemas import (
    FIT_ANALYSIS_VERSION,
    CvExtractionResponse,
    CvExtractionResult,
    FitAnalysisResult,
    FitCandidateSnapshot,
    FitJobSnapshot,
    FitLlmEvidence,
    map_fit_level,
)
from app.ai.agents.recruitment.service import CvExtractionService

__all__ = [
    "FIT_ANALYSIS_VERSION",
    "CvExtractionResponse",
    "CvExtractionResult",
    "CvExtractionService",
    "FitAnalysisResult",
    "FitAnalysisService",
    "FitCandidateSnapshot",
    "FitJobSnapshot",
    "FitLlmEvidence",
    "RecruitmentExtractionError",
    "RecruitmentExtractionUnsupportedError",
    "RecruitmentExtractionValidationError",
    "RecruitmentFitError",
    "RecruitmentFitValidationError",
    "map_fit_level",
]
