"""Pydantic schemas for CV extraction (6.1), fit analysis (6.2), and recruitment agent (6.3A)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.ai.core.context.models import AIExecutionContext

FitLevel = Literal["BAD", "MEDIUM", "GOOD"]

FIT_ANALYSIS_VERSION = "1"

# Deterministic thresholds (service maps score → level; LLM must not invent labels).
FIT_SCORE_BAD_MAX = 49
FIT_SCORE_MEDIUM_MAX = 74
FIT_SCORE_MAX = 100


class ExtractedEducation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    institution: str | None = None
    degree: str | None = None
    field_of_study: str | None = None
    start_year: int | None = Field(default=None, ge=1950, le=2100)
    end_year: int | None = Field(default=None, ge=1950, le=2100)


class ExtractedExperience(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: str | None = None
    title: str | None = None
    start_year: int | None = Field(default=None, ge=1950, le=2100)
    end_year: int | None = Field(default=None, ge=1950, le=2100)
    description: str | None = None


class CvExtractionResult(BaseModel):
    """Validated structured CV fields for form pre-fill. Not persisted as source of truth."""

    model_config = ConfigDict(extra="forbid")

    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    education: list[ExtractedEducation] = Field(default_factory=list)
    experience: list[ExtractedExperience] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)


class CvExtractionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    extraction: CvExtractionResult


class FitJobSnapshot(BaseModel):
    """Compact job requirements for fit analysis (no DB models)."""

    model_config = ConfigDict(extra="forbid")

    title: str
    description: str
    requirements: str | None = None
    employment_type: str
    internship_duration_months: int | None = None


class FitEducationSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    institution: str
    degree: str | None = None
    field_of_study: str | None = None
    start_year: int | None = None
    end_year: int | None = None


class FitExperienceSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: str
    title: str
    start_year: int | None = None
    end_year: int | None = None
    description: str | None = None


class FitAnswerSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str
    value: str


class FitCandidateSnapshot(BaseModel):
    """Structured application data for fit analysis."""

    model_config = ConfigDict(extra="forbid")

    education: list[FitEducationSnapshot] = Field(default_factory=list)
    experience: list[FitExperienceSnapshot] = Field(default_factory=list)
    answers: list[FitAnswerSnapshot] = Field(default_factory=list)


class FitLlmEvidence(BaseModel):
    """Raw structured evidence from the LLM (no fit_level)."""

    model_config = ConfigDict(extra="forbid")

    fit_score: int = Field(ge=0, le=FIT_SCORE_MAX)
    matching_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    experience_match: str = Field(min_length=1, max_length=500)
    education_match: str = Field(min_length=1, max_length=500)
    explanation: str = Field(min_length=1, max_length=2000)


class FitAnalysisResult(BaseModel):
    """Validated fit assessment: LLM evidence + deterministic fit_level."""

    model_config = ConfigDict(extra="forbid")

    fit_score: int = Field(ge=0, le=FIT_SCORE_MAX)
    fit_level: FitLevel
    matching_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    experience_match: str
    education_match: str
    explanation: str
    analysis_version: str = FIT_ANALYSIS_VERSION


def map_fit_level(score: int) -> FitLevel:
    """Map a clamped 0–100 score to BAD / MEDIUM / GOOD."""
    if score < 0 or score > FIT_SCORE_MAX:
        raise ValueError(f"fit_score must be 0–{FIT_SCORE_MAX}, got {score}")
    if score <= FIT_SCORE_BAD_MAX:
        return "BAD"
    if score <= FIT_SCORE_MEDIUM_MAX:
        return "MEDIUM"
    return "GOOD"


# --- Recruitment Agent (Phase 6.3A) ---


class RecruitmentAgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    question: str
    context: AIExecutionContext


class RecruitmentAgentUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_tokens: int | None = None
    output_tokens: int | None = None
    thinking_tokens: int | None = None
    total_tokens: int | None = None


class RecruitmentAgentAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    model: str
    tool_names_called: list[str] = Field(default_factory=list)
    usage: RecruitmentAgentUsage | None = None
