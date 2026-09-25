"""Phase 5.10 RAG evaluation schemas (offline fixtures + result reports)."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvaluationCaseKind(str, Enum):
    RETRIEVAL = "retrieval"
    ABSTENTION = "abstention"
    SECURITY = "security"
    CITATION = "citation"
    LIVE = "live"


class FixtureCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    citation_id: int
    chunk_id: int
    company_document_id: int
    page_start: int
    page_end: int
    document_name: str | None = None
    content_hash: str


class FixtureContextItem(BaseModel):
    """Minimal context item for offline citation checks."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: int
    company_document_id: int
    content: str
    page_start: int
    page_end: int
    chunk_index: int = 0
    content_hash: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    rrf_score: float = 1.0


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: EvaluationCaseKind
    question: str = ""
    relevant_document_ids: list[int] = Field(default_factory=list)
    relevant_chunk_ids: list[int] | None = None
    expected_answer_facts: list[str] | None = None
    should_abstain: bool = False
    expected_citation_document_ids: list[int] | None = None
    # Offline fixtures (no Gemini)
    fixture_ranked_document_ids: list[int] | None = None
    fixture_ranked_chunk_ids: list[int] | None = None
    fixture_answer: str | None = None
    fixture_citations: list[FixtureCitation] | None = None
    fixture_context: list[FixtureContextItem] | None = None
    fixture_invalid_citation_ids: list[int] | None = None
    notes: str | None = None


class RetrievalMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recall_at_1: float | None = None
    recall_at_3: float | None = None
    recall_at_5: float | None = None
    precision_at_1: float | None = None
    precision_at_3: float | None = None
    precision_at_5: float | None = None
    mrr: float | None = None


class CitationChecks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    all_citation_ids_valid: bool = False
    citations_match_context: bool = False
    invalid_citation_ids: list[int] = Field(default_factory=list)
    citation_less: bool = False
    passed: bool = False
    details: list[str] = Field(default_factory=list)


class GenerationChecks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer_non_empty: bool = False
    abstained_as_expected: bool = False
    facts_present: bool = False
    unsupported_citations: bool = False
    llm_not_called_on_abstention: bool | None = None
    passed: bool = False
    details: list[str] = Field(default_factory=list)


class SecurityChecks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_archived_filtered: bool = False
    hr_can_access_archived: bool = False
    unauthorized_excluded: bool = False
    private_docs_isolated: bool = False
    candidate_cvs_isolated: bool = False
    prompt_injection_structure_ok: bool = False
    passed: bool = False
    details: list[str] = Field(default_factory=list)


class EvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    passed: bool
    retrieval_metrics: RetrievalMetrics | None = None
    citation_checks: CitationChecks | None = None
    generation_checks: GenerationChecks | None = None
    security_checks: SecurityChecks | None = None
    errors: list[str] = Field(default_factory=list)


class EvaluationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_cases: int = 0
    passed_cases: int = 0
    failed_cases: int = 0
    recall_at_1: float | None = None
    recall_at_3: float | None = None
    recall_at_5: float | None = None
    precision_at_1: float | None = None
    precision_at_3: float | None = None
    precision_at_5: float | None = None
    mrr: float | None = None
    citation_validity_rate: float | None = None
    abstention_accuracy: float | None = None
    security_checks_passed: bool | None = None
    gemini_embed_calls: int = 0
    gemini_generate_calls: int = 0
    results: list[EvaluationResult] = Field(default_factory=list)
