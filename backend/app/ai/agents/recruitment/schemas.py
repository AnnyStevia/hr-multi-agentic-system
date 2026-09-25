"""Pydantic schemas for CV structured extraction (Phase 6.1)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


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
