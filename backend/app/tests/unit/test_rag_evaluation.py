"""Unit tests for Phase 5.10 RAG evaluation (no Gemini / no PG)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.ai.evaluation.datasets import GOLDEN_CASES, load_golden_dataset, validate_dataset
from app.ai.evaluation.generation import (
    evaluate_abstention_offline,
    evaluate_citations,
    evaluate_generation,
)
from app.ai.evaluation.retrieval import (
    compute_retrieval_metrics,
    mean_reciprocal_rank,
    precision_at_k,
    recall_at_k,
)
from app.ai.evaluation.runner import aggregate_summary, format_report, run_offline
from app.ai.evaluation.schemas import (
    EvaluationCase,
    EvaluationCaseKind,
    EvaluationResult,
    FixtureCitation,
    FixtureContextItem,
    RetrievalMetrics,
)
from app.ai.evaluation.security import evaluate_security
from app.ai.rag.generation.service import NO_CONTEXT_ABSTENTION


def test_dataset_validation_and_size():
    cases = validate_dataset()
    assert len(cases) == 5
    assert len(GOLDEN_CASES) == 5
    ids = {c.id for c in cases}
    assert "internship_position_retrieval" in ids
    assert "no_context_abstention" in ids
    assert "security_employee_archived" in ids


def test_dataset_rejects_extra_fields():
    with pytest.raises(ValidationError):
        EvaluationCase(
            id="bad",
            kind=EvaluationCaseKind.RETRIEVAL,
            invented_field=True,  # type: ignore[call-arg]
        )


def test_load_golden_dataset_roundtrip():
    cases = load_golden_dataset()
    assert all(isinstance(c, EvaluationCase) for c in cases)


def test_recall_at_k():
    relevant = [2]
    ranked = [2, 5, 7]
    assert recall_at_k(relevant, ranked, 1) == 1.0
    assert recall_at_k(relevant, ranked, 3) == 1.0
    assert recall_at_k([2, 9], [5, 7, 2], 2) == 0.0
    assert recall_at_k([2, 9], [5, 2, 9], 3) == 1.0
    assert recall_at_k([], [1, 2], 1) == 0.0


def test_precision_at_k():
    assert precision_at_k([2], [2, 5, 7], 1) == 1.0
    assert precision_at_k([2], [2, 5, 7], 3) == pytest.approx(1 / 3)
    assert precision_at_k([2], [], 1) == 0.0


def test_mrr():
    assert mean_reciprocal_rank([2], [5, 2, 7]) == pytest.approx(0.5)
    assert mean_reciprocal_rank([2], [2, 5]) == 1.0
    assert mean_reciprocal_rank([2], [5, 7]) == 0.0
    assert mean_reciprocal_rank([], [1]) == 0.0


def test_compute_retrieval_metrics_keys():
    metrics = compute_retrieval_metrics([2], [2, 5, 7])
    assert set(metrics) >= {
        "recall_at_1",
        "recall_at_3",
        "recall_at_5",
        "precision_at_1",
        "precision_at_3",
        "precision_at_5",
        "mrr",
    }
    assert metrics["mrr"] == 1.0


def test_citation_valid():
    ctx = [
        FixtureContextItem(
            chunk_id=10,
            company_document_id=2,
            content="AI Software Engineer internship",
            page_start=1,
            page_end=1,
            content_hash="h1",
        )
    ]
    citations = [
        FixtureCitation(
            citation_id=1,
            chunk_id=10,
            company_document_id=2,
            page_start=1,
            page_end=1,
            content_hash="h1",
        )
    ]
    checks = evaluate_citations(
        answer_text="She was an AI Software Engineer. [1]",
        citations=citations,
        context_items=ctx,
    )
    assert checks.passed
    assert checks.all_citation_ids_valid
    assert checks.citations_match_context
    assert not checks.citation_less


def test_citation_invalid_detection():
    ctx = [
        FixtureContextItem(
            chunk_id=10,
            company_document_id=2,
            content="x",
            page_start=1,
            page_end=1,
            content_hash="h1",
        )
    ]
    checks = evaluate_citations(
        answer_text="Bad marker. [99]",
        citations=[],
        context_items=ctx,
        expected_invalid_ids=[99],
    )
    assert checks.passed
    assert 99 in checks.invalid_citation_ids


def test_citation_less_answer():
    checks = evaluate_citations(
        answer_text=NO_CONTEXT_ABSTENTION,
        citations=[],
        context_items=[],
    )
    assert checks.citation_less
    assert checks.passed


def test_citation_document_mismatch_fails():
    ctx = [
        FixtureContextItem(
            chunk_id=10,
            company_document_id=2,
            content="x",
            page_start=1,
            page_end=1,
            content_hash="h1",
        )
    ]
    citations = [
        FixtureCitation(
            citation_id=1,
            chunk_id=10,
            company_document_id=99,
            page_start=1,
            page_end=1,
            content_hash="h1",
        )
    ]
    checks = evaluate_citations(
        answer_text="Claim. [1]",
        citations=citations,
        context_items=ctx,
    )
    assert not checks.passed
    assert not checks.citations_match_context


def test_abstention_offline_no_llm():
    gen, cite = evaluate_abstention_offline()
    assert gen.passed
    assert cite.passed
    assert gen.llm_not_called_on_abstention is True
    assert gen.abstained_as_expected


def test_generation_facts_and_abstention_flags():
    ok = evaluate_generation(
        answer_text="AI Software Engineer role. [1]",
        should_abstain=False,
        expected_facts=["AI Software Engineer"],
    )
    assert ok.passed
    assert ok.facts_present

    bad = evaluate_generation(
        answer_text="Something else",
        should_abstain=False,
        expected_facts=["AI Software Engineer"],
    )
    assert not bad.passed


def test_security_checks_pass():
    checks = evaluate_security()
    assert checks.passed
    assert checks.employee_archived_filtered
    assert checks.hr_can_access_archived
    assert checks.unauthorized_excluded
    assert checks.private_docs_isolated
    assert checks.candidate_cvs_isolated
    assert checks.prompt_injection_structure_ok


def test_offline_runner_all_pass():
    summary = run_offline()
    assert summary.total_cases == 5
    assert summary.failed_cases == 0
    assert summary.passed_cases == 5
    assert summary.gemini_embed_calls == 0
    assert summary.gemini_generate_calls == 0
    assert summary.security_checks_passed is True
    assert summary.abstention_accuracy == 1.0
    assert summary.citation_validity_rate == 1.0
    report = format_report(summary)
    assert "RAG Evaluation" in report
    assert "No Gemini calls performed." in report
    assert "PASS" in report


def test_aggregate_summary():
    results = [
        EvaluationResult(
            case_id="a",
            passed=True,
            retrieval_metrics=RetrievalMetrics(
                recall_at_1=1.0,
                recall_at_3=1.0,
                recall_at_5=1.0,
                precision_at_1=1.0,
                precision_at_3=0.5,
                precision_at_5=0.4,
                mrr=1.0,
            ),
        ),
        EvaluationResult(case_id="b", passed=False, errors=["x"]),
    ]
    summary = aggregate_summary(results)
    assert summary.total_cases == 2
    assert summary.passed_cases == 1
    assert summary.failed_cases == 1
    assert summary.recall_at_1 == 1.0
    assert summary.mrr == 1.0
