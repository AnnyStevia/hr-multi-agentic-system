"""Golden evaluation dataset (Pydantic fixtures; no invented HR facts)."""

from __future__ import annotations

from app.ai.evaluation.schemas import (
    EvaluationCase,
    EvaluationCaseKind,
    FixtureCitation,
    FixtureContextItem,
)

# TODO(future cases): office location / Casablanca once more indexed docs exist.
# TODO(future cases): multi-document citation ranking once corpus grows.

_CONTEXT_DOC2 = FixtureContextItem(
    chunk_id=101,
    company_document_id=2,
    content=(
        "During her internship, Anny Stevia held the position of "
        "AI Software Engineer."
    ),
    page_start=1,
    page_end=1,
    chunk_index=0,
    content_hash="eval-fixture-doc2-hash",
)

GOLDEN_CASES: list[EvaluationCase] = [
    EvaluationCase(
        id="internship_position_retrieval",
        kind=EvaluationCaseKind.RETRIEVAL,
        question="What position did Anny Stevia hold during her internship?",
        relevant_document_ids=[2],
        expected_answer_facts=["AI Software Engineer"],
        should_abstain=False,
        expected_citation_document_ids=[2],
        # Offline ranking fixture: doc 2 at rank 1 (simulates hybrid hit order)
        fixture_ranked_document_ids=[2, 5, 7],
        fixture_answer="Anny Stevia held an AI Software Engineer internship. [1]",
        fixture_citations=[
            FixtureCitation(
                citation_id=1,
                chunk_id=101,
                company_document_id=2,
                page_start=1,
                page_end=1,
                document_name="Company PDF",
                content_hash="eval-fixture-doc2-hash",
            )
        ],
        fixture_context=[_CONTEXT_DOC2],
        notes="Live eval (--live-generation) requires local company document id=2.",
    ),
    EvaluationCase(
        id="no_context_abstention",
        kind=EvaluationCaseKind.ABSTENTION,
        question="What is the secret bonus policy for 2099?",
        relevant_document_ids=[],
        should_abstain=True,
        fixture_ranked_document_ids=[],
    ),
    EvaluationCase(
        id="citation_integrity_valid",
        kind=EvaluationCaseKind.CITATION,
        question="What position did Anny Stevia hold during her internship?",
        relevant_document_ids=[2],
        should_abstain=False,
        expected_citation_document_ids=[2],
        fixture_answer="She was an AI Software Engineer. [1]",
        fixture_citations=[
            FixtureCitation(
                citation_id=1,
                chunk_id=101,
                company_document_id=2,
                page_start=1,
                page_end=1,
                content_hash="eval-fixture-doc2-hash",
            )
        ],
        fixture_context=[_CONTEXT_DOC2],
    ),
    EvaluationCase(
        id="citation_integrity_invalid",
        kind=EvaluationCaseKind.CITATION,
        question="What position did Anny Stevia hold during her internship?",
        relevant_document_ids=[2],
        should_abstain=False,
        fixture_answer="Fabricated claim with a bad marker. [99]",
        fixture_citations=[],
        fixture_context=[_CONTEXT_DOC2],
        fixture_invalid_citation_ids=[99],
    ),
    EvaluationCase(
        id="security_employee_archived",
        kind=EvaluationCaseKind.SECURITY,
        question="",
        relevant_document_ids=[],
        should_abstain=False,
        notes="Deterministic ACL / isolation / prompt-injection structure checks.",
    ),
]


def load_golden_dataset() -> list[EvaluationCase]:
    """Return a validated copy of the golden cases."""
    return [EvaluationCase.model_validate(case.model_dump()) for case in GOLDEN_CASES]


def validate_dataset(cases: list[EvaluationCase] | None = None) -> list[EvaluationCase]:
    cases = cases if cases is not None else load_golden_dataset()
    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate evaluation case ids")
    for case in cases:
        EvaluationCase.model_validate(case.model_dump())
    return cases
