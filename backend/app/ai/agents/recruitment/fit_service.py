"""Candidate ↔ job fit analysis (Phase 6.2). Does not re-run CV extraction."""

from __future__ import annotations

import json

from pydantic import ValidationError

from app.ai.agents.recruitment.exceptions import (
    RecruitmentFitError,
    RecruitmentFitValidationError,
)
from app.ai.agents.recruitment.prompts import (
    FIT_ANALYSIS_JSON_SCHEMA,
    FIT_ANALYSIS_SYSTEM_PROMPT,
    build_fit_analysis_user_message,
)
from app.ai.agents.recruitment.schemas import (
    FIT_ANALYSIS_VERSION,
    FIT_SCORE_MAX,
    FitAnalysisResult,
    FitCandidateSnapshot,
    FitJobSnapshot,
    FitLlmEvidence,
    map_fit_level,
)
from app.ai.core.exceptions import LLMConfigurationError, LLMProviderError
from app.ai.core.llm import get_llm_provider
from app.ai.core.llm.base import LLMMessage, LLMProvider
from app.ai.rag.exceptions import DocumentParseError, UnsupportedDocumentError
from app.ai.rag.ingestion.parsers.pdf import PDF_MIME, PdfDocumentParser

DEFAULT_MAX_JOB_CHARS = 4_000
DEFAULT_MAX_CANDIDATE_CHARS = 4_000
DEFAULT_MAX_CV_CHARS = 8_000
DEFAULT_MAX_OUTPUT_TOKENS = 800
DEFAULT_TEMPERATURE = 0.1
DEFAULT_MAX_SKILL_ITEMS = 20


class FitAnalysisService:
    """One structured LLM call: job + application (+ optional CV text) → fit assessment."""

    def __init__(
        self,
        *,
        llm_provider: LLMProvider | None = None,
        pdf_parser: PdfDocumentParser | None = None,
        max_job_chars: int = DEFAULT_MAX_JOB_CHARS,
        max_candidate_chars: int = DEFAULT_MAX_CANDIDATE_CHARS,
        max_cv_chars: int = DEFAULT_MAX_CV_CHARS,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> None:
        self._llm = llm_provider if llm_provider is not None else get_llm_provider()
        self._parser = pdf_parser if pdf_parser is not None else PdfDocumentParser()
        self._max_job_chars = max_job_chars
        self._max_candidate_chars = max_candidate_chars
        self._max_cv_chars = max_cv_chars
        self._max_output_tokens = max_output_tokens
        self._temperature = temperature

    def analyze(
        self,
        *,
        job: FitJobSnapshot,
        candidate: FitCandidateSnapshot,
        cv_text: str | None = None,
    ) -> FitAnalysisResult:
        job_block = self._format_job(job)[: self._max_job_chars]
        candidate_block = self._format_candidate(candidate)[: self._max_candidate_chars]
        capped_cv = (cv_text or "").strip()[: self._max_cv_chars] or None

        messages = [
            LLMMessage(role="system", content=FIT_ANALYSIS_SYSTEM_PROMPT),
            LLMMessage(
                role="user",
                content=build_fit_analysis_user_message(
                    job_block=job_block,
                    candidate_block=candidate_block,
                    cv_text=capped_cv,
                ),
            ),
        ]
        try:
            response = self._llm.generate_structured(
                messages,
                schema=FIT_ANALYSIS_JSON_SCHEMA,
                temperature=self._temperature,
                max_tokens=self._max_output_tokens,
            )
        except LLMConfigurationError as exc:
            raise RecruitmentFitError("Fit analysis is not configured") from exc
        except LLMProviderError as exc:
            raise RecruitmentFitError("Fit analysis failed") from exc

        try:
            evidence = FitLlmEvidence.model_validate(response.data)
        except ValidationError as exc:
            raise RecruitmentFitValidationError(
                "Fit analysis returned invalid structured data"
            ) from exc

        return self.normalize(evidence)

    def normalize(self, evidence: FitLlmEvidence) -> FitAnalysisResult:
        """Clamp score, map fit_level deterministically, trim skill lists."""
        score = max(0, min(FIT_SCORE_MAX, int(evidence.fit_score)))
        return FitAnalysisResult(
            fit_score=score,
            fit_level=map_fit_level(score),
            matching_skills=_trim_skills(evidence.matching_skills),
            missing_skills=_trim_skills(evidence.missing_skills),
            experience_match=evidence.experience_match.strip()[:500],
            education_match=evidence.education_match.strip()[:500],
            explanation=evidence.explanation.strip()[:2000],
            analysis_version=FIT_ANALYSIS_VERSION,
        )

    def extract_cv_text(self, content: bytes, *, filename: str, content_type: str) -> str | None:
        """Parse PDF CV bytes to text. Returns None for non-PDF or empty text."""
        if content_type != PDF_MIME and not filename.lower().endswith(".pdf"):
            return None
        if not self._parser.supports(PDF_MIME, filename):
            return None
        try:
            pages = self._parser.parse(content)
        except (UnsupportedDocumentError, DocumentParseError):
            return None
        text = "\n\n".join(page.text for page in pages if page.text).strip()
        return text[: self._max_cv_chars] if text else None

    def _format_job(self, job: FitJobSnapshot) -> str:
        lines = [
            f"title: {job.title}",
            f"employment_type: {job.employment_type}",
        ]
        if job.internship_duration_months is not None:
            lines.append(f"internship_duration_months: {job.internship_duration_months}")
        if job.requirements:
            lines.append(f"requirements:\n{job.requirements}")
        lines.append(f"description:\n{job.description}")
        return "\n".join(lines)

    def _format_candidate(self, candidate: FitCandidateSnapshot) -> str:
        payload = {
            "education": [item.model_dump() for item in candidate.education],
            "experience": [item.model_dump() for item in candidate.experience],
            "answers": [item.model_dump() for item in candidate.answers],
        }
        return json.dumps(payload, ensure_ascii=False)


def _trim_skills(items: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in items:
        skill = (raw or "").strip()
        if not skill:
            continue
        key = skill.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(skill[:80])
        if len(cleaned) >= DEFAULT_MAX_SKILL_ITEMS:
            break
    return cleaned
