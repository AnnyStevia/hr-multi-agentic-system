"""Unit tests for FitAnalysisService (mocked LLM; no Gemini credits)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.ai.agents.recruitment import (
    FitAnalysisService,
    FitCandidateSnapshot,
    FitJobSnapshot,
    FitLlmEvidence,
    RecruitmentFitError,
    RecruitmentFitValidationError,
    map_fit_level,
)
from app.ai.agents.recruitment.schemas import (
    FIT_SCORE_BAD_MAX,
    FIT_SCORE_MEDIUM_MAX,
)
from app.ai.core.exceptions import LLMProviderError
from app.ai.core.llm.base import LLMStructuredResponse, LLMUsage


def _job(**overrides) -> FitJobSnapshot:
    data = {
        "title": "Backend Engineer",
        "description": "Build APIs with Python and FastAPI.",
        "requirements": "Python, FastAPI, PostgreSQL. Kubernetes is a plus.",
        "employment_type": "full_time",
        "internship_duration_months": None,
    }
    data.update(overrides)
    return FitJobSnapshot(**data)


def _candidate() -> FitCandidateSnapshot:
    return FitCandidateSnapshot(
        education=[
            {
                "institution": "INSAT",
                "degree": "Engineering",
                "field_of_study": "Software",
                "start_year": 2020,
                "end_year": 2025,
            }
        ],
        experience=[
            {
                "company": "Acme",
                "title": "Backend Developer",
                "start_year": 2023,
                "end_year": None,
                "description": "Python FastAPI PostgreSQL",
            }
        ],
        answers=[{"prompt": "Years of Python?", "value": "3"}],
    )


def _llm_payload(**overrides) -> dict:
    data = {
        "fit_score": 82,
        "matching_skills": ["Python", "FastAPI", "PostgreSQL"],
        "missing_skills": ["Kubernetes"],
        "experience_match": "Strong match for backend experience.",
        "education_match": "Relevant software engineering education.",
        "explanation": (
            "The candidate matches the required Python and FastAPI skills and has "
            "approximately three years of backend experience. Kubernetes experience "
            "was not identified in the provided candidate information."
        ),
    }
    data.update(overrides)
    return data


def _service_with(llm: MagicMock) -> FitAnalysisService:
    return FitAnalysisService(llm_provider=llm)


@pytest.mark.parametrize(
    "score,expected",
    [
        (0, "BAD"),
        (FIT_SCORE_BAD_MAX, "BAD"),
        (FIT_SCORE_BAD_MAX + 1, "MEDIUM"),
        (FIT_SCORE_MEDIUM_MAX, "MEDIUM"),
        (FIT_SCORE_MEDIUM_MAX + 1, "GOOD"),
        (100, "GOOD"),
    ],
)
def test_map_fit_level_thresholds(score, expected):
    assert map_fit_level(score) == expected


def test_map_fit_level_rejects_out_of_range():
    with pytest.raises(ValueError):
        map_fit_level(-1)
    with pytest.raises(ValueError):
        map_fit_level(101)


def test_strong_match_normalizes_good():
    llm = MagicMock()
    llm.generate_structured.return_value = LLMStructuredResponse(
        data=_llm_payload(fit_score=82),
        model="mock",
        usage=LLMUsage(total_tokens=1),
    )
    result = _service_with(llm).analyze(job=_job(), candidate=_candidate())
    assert result.fit_score == 82
    assert result.fit_level == "GOOD"
    assert "Python" in result.matching_skills
    assert "Kubernetes" in result.missing_skills
    assert "hire" not in result.explanation.lower()
    assert result.analysis_version == "1"


def test_medium_and_weak_match():
    llm = MagicMock()
    llm.generate_structured.return_value = LLMStructuredResponse(
        data=_llm_payload(fit_score=60, matching_skills=["Python"], missing_skills=["FastAPI", "K8s"]),
        model="mock",
        usage=LLMUsage(total_tokens=1),
    )
    medium = _service_with(llm).analyze(job=_job(), candidate=_candidate())
    assert medium.fit_level == "MEDIUM"

    llm.generate_structured.return_value = LLMStructuredResponse(
        data=_llm_payload(fit_score=20, matching_skills=[], missing_skills=["Python", "FastAPI"]),
        model="mock",
        usage=LLMUsage(total_tokens=1),
    )
    weak = _service_with(llm).analyze(job=_job(), candidate=_candidate())
    assert weak.fit_level == "BAD"
    assert weak.fit_score == 20


def test_normalize_clamps_and_ignores_llm_level_label():
    service = FitAnalysisService(llm_provider=MagicMock())
    # Bypass Field(le=100) to verify service-side clamp defensively.
    evidence = FitLlmEvidence.model_construct(
        fit_score=150,
        matching_skills=["Python", "Python", "  ", "FastAPI"],
        missing_skills=["Kubernetes"],
        experience_match="ok",
        education_match="ok",
        explanation="evidence only",
    )
    result = service.normalize(evidence)
    assert result.fit_score == 100
    assert result.fit_level == "GOOD"
    assert result.matching_skills == ["Python", "FastAPI"]


def test_employment_type_included_in_prompt():
    llm = MagicMock()
    llm.generate_structured.return_value = LLMStructuredResponse(
        data=_llm_payload(fit_score=70),
        model="mock",
        usage=LLMUsage(total_tokens=1),
    )
    job = _job(employment_type="internship", internship_duration_months=6)
    _service_with(llm).analyze(job=job, candidate=_candidate(), cv_text="Python")
    user_msg = llm.generate_structured.call_args.args[0][1].content
    assert "internship" in user_msg
    assert "internship_duration_months: 6" in user_msg
    kwargs = llm.generate_structured.call_args.kwargs
    assert kwargs["max_tokens"] == 800
    assert kwargs["temperature"] == 0.1


def test_invalid_llm_output_raises_validation():
    llm = MagicMock()
    llm.generate_structured.return_value = LLMStructuredResponse(
        data={"fit_score": "nope"},
        model="mock",
        usage=LLMUsage(total_tokens=1),
    )
    with pytest.raises(RecruitmentFitValidationError):
        _service_with(llm).analyze(job=_job(), candidate=_candidate())


def test_llm_failure_raises_fit_error():
    llm = MagicMock()
    llm.generate_structured.side_effect = LLMProviderError("down")
    with pytest.raises(RecruitmentFitError):
        _service_with(llm).analyze(job=_job(), candidate=_candidate())


def test_fit_analysis_does_not_index_rag():
    llm = MagicMock()
    llm.generate_structured.return_value = LLMStructuredResponse(
        data=_llm_payload(),
        model="mock",
        usage=LLMUsage(total_tokens=1),
    )
    with patch("app.ai.rag.indexing.service.CompanyDocumentIndexingService") as indexing:
        _service_with(llm).analyze(job=_job(), candidate=_candidate())
        indexing.assert_not_called()
