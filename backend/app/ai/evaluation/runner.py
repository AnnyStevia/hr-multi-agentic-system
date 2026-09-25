"""RAG evaluation runner — offline by default; --live-generation is opt-in.

Usage (from backend/ with PYTHONPATH=.):

  python -m app.ai.evaluation.runner
  python -m app.ai.evaluation.runner --live-generation
  python -m app.ai.evaluation.runner --json
"""

from __future__ import annotations

import argparse
import json
import sys
from statistics import mean

from app.ai.evaluation.datasets import load_golden_dataset, validate_dataset
from app.ai.evaluation.generation import (
    evaluate_abstention_offline,
    evaluate_citations,
    evaluate_generation,
)
from app.ai.evaluation.retrieval import compute_retrieval_metrics
from app.ai.evaluation.schemas import (
    EvaluationCase,
    EvaluationCaseKind,
    EvaluationResult,
    EvaluationSummary,
    RetrievalMetrics,
)
from app.ai.evaluation.security import evaluate_security


def _avg(values: list[float]) -> float | None:
    return mean(values) if values else None


def run_case_offline(case: EvaluationCase) -> EvaluationResult:
    errors: list[str] = []
    retrieval_metrics = None
    citation_checks = None
    generation_checks = None
    security_checks = None

    try:
        if case.kind == EvaluationCaseKind.SECURITY:
            security_checks = evaluate_security()
            return EvaluationResult(
                case_id=case.id,
                passed=security_checks.passed,
                security_checks=security_checks,
                errors=security_checks.details if not security_checks.passed else [],
            )

        if case.kind == EvaluationCaseKind.ABSTENTION:
            generation_checks, citation_checks = evaluate_abstention_offline()
            return EvaluationResult(
                case_id=case.id,
                passed=generation_checks.passed and citation_checks.passed,
                citation_checks=citation_checks,
                generation_checks=generation_checks,
                errors=(generation_checks.details + citation_checks.details)
                if not (generation_checks.passed and citation_checks.passed)
                else [],
            )

        if case.fixture_ranked_document_ids is not None and case.relevant_document_ids:
            metrics = compute_retrieval_metrics(
                case.relevant_document_ids,
                case.fixture_ranked_document_ids,
            )
            retrieval_metrics = RetrievalMetrics(**metrics)

        if case.fixture_context is not None and case.fixture_answer is not None:
            citation_checks = evaluate_citations(
                answer_text=case.fixture_answer,
                citations=case.fixture_citations or [],
                context_items=case.fixture_context,
                expected_invalid_ids=case.fixture_invalid_citation_ids,
            )
            generation_checks = evaluate_generation(
                answer_text=case.fixture_answer,
                should_abstain=case.should_abstain,
                expected_facts=case.expected_answer_facts,
                citation_checks=citation_checks,
                expect_invalid_citations=bool(case.fixture_invalid_citation_ids),
            )

        passed_parts: list[bool] = []
        if retrieval_metrics is not None:
            # Require perfect recall@1 for positive retrieval fixtures
            passed_parts.append((retrieval_metrics.recall_at_1 or 0.0) >= 1.0)
        if citation_checks is not None:
            passed_parts.append(citation_checks.passed)
        if generation_checks is not None:
            passed_parts.append(generation_checks.passed)

        passed = all(passed_parts) if passed_parts else False
        if not passed_parts:
            errors.append("no checks executed for case")
            passed = False

        if citation_checks and not citation_checks.passed:
            errors.extend(citation_checks.details)
        if generation_checks and not generation_checks.passed:
            errors.extend(generation_checks.details)

        return EvaluationResult(
            case_id=case.id,
            passed=passed,
            retrieval_metrics=retrieval_metrics,
            citation_checks=citation_checks,
            generation_checks=generation_checks,
            errors=errors,
        )
    except Exception as exc:  # noqa: BLE001
        return EvaluationResult(
            case_id=case.id,
            passed=False,
            errors=[str(exc)],
        )


def aggregate_summary(
    results: list[EvaluationResult],
    *,
    gemini_embed_calls: int = 0,
    gemini_generate_calls: int = 0,
) -> EvaluationSummary:
    recall1: list[float] = []
    recall3: list[float] = []
    recall5: list[float] = []
    prec1: list[float] = []
    prec3: list[float] = []
    prec5: list[float] = []
    mrrs: list[float] = []
    citation_pass = 0
    citation_total = 0
    abstention_pass = 0
    abstention_total = 0
    security_passed: bool | None = None

    for result in results:
        if result.retrieval_metrics:
            rm = result.retrieval_metrics
            if rm.recall_at_1 is not None:
                recall1.append(rm.recall_at_1)
            if rm.recall_at_3 is not None:
                recall3.append(rm.recall_at_3)
            if rm.recall_at_5 is not None:
                recall5.append(rm.recall_at_5)
            if rm.precision_at_1 is not None:
                prec1.append(rm.precision_at_1)
            if rm.precision_at_3 is not None:
                prec3.append(rm.precision_at_3)
            if rm.precision_at_5 is not None:
                prec5.append(rm.precision_at_5)
            if rm.mrr is not None:
                mrrs.append(rm.mrr)

        if result.citation_checks is not None:
            citation_total += 1
            if result.citation_checks.passed:
                citation_pass += 1

        if result.generation_checks is not None and result.case_id == "no_context_abstention":
            abstention_total += 1
            if result.generation_checks.passed:
                abstention_pass += 1

        if result.security_checks is not None:
            security_passed = (
                result.security_checks.passed
                if security_passed is None
                else security_passed and result.security_checks.passed
            )

    passed = sum(1 for r in results if r.passed)
    return EvaluationSummary(
        total_cases=len(results),
        passed_cases=passed,
        failed_cases=len(results) - passed,
        recall_at_1=_avg(recall1),
        recall_at_3=_avg(recall3),
        recall_at_5=_avg(recall5),
        precision_at_1=_avg(prec1),
        precision_at_3=_avg(prec3),
        precision_at_5=_avg(prec5),
        mrr=_avg(mrrs),
        citation_validity_rate=(
            citation_pass / citation_total if citation_total else None
        ),
        abstention_accuracy=(
            abstention_pass / abstention_total if abstention_total else None
        ),
        security_checks_passed=security_passed,
        gemini_embed_calls=gemini_embed_calls,
        gemini_generate_calls=gemini_generate_calls,
        results=results,
    )


def run_offline() -> EvaluationSummary:
    cases = validate_dataset(load_golden_dataset())
    results = [run_case_offline(case) for case in cases]
    return aggregate_summary(results)


def run_live_generation() -> EvaluationSummary:
    """Opt-in live Knowledge Agent evaluation (1 embed + 1 generate)."""
    from app.modules.identity import models as identity_models  # noqa: F401
    from app.modules.employees import models as employee_models  # noqa: F401
    from app.modules.documents import models as document_models  # noqa: F401
    from app.ai.rag import models as rag_models  # noqa: F401

    from app.ai.core.context.models import AIExecutionContext
    from app.ai.core.llm import get_llm_provider
    from app.ai.rag.config import rag_settings
    from app.ai.rag.embeddings import EmbeddingService, get_embedding_provider
    from app.ai.rag.generation import GroundedGenerationService
    from app.ai.rag.generation.schemas import RAGGenerationRequest
    from app.ai.rag.query import RAGQueryService
    from app.ai.rag.query.schemas import RAGQueryRequest
    from app.ai.rag.retrieval import COMPANY_DOCUMENTS_READ, HybridRetrievalService
    from app.core.database import SessionLocal
    from app.modules.identity.models import Permission, Role, RolePermission, User, UserRole

    query = "What position did Anny Stevia hold during her internship?"

    class _CountingEmbeddingProvider:
        def __init__(self, inner):
            self._inner = inner
            self.embed_calls = 0

        def embed_text(self, text: str, *, task_type: str | None = None):
            self.embed_calls += 1
            return self._inner.embed_text(text, task_type=task_type)

        def embed_texts(self, texts, *, task_type: str | None = None):
            self.embed_calls += len(list(texts))
            return self._inner.embed_texts(texts, task_type=task_type)

    class _CountingLLMProvider:
        def __init__(self, inner):
            self._inner = inner
            self.generate_calls = 0

        def generate_text(self, messages, *, temperature=None, max_tokens=None):
            self.generate_calls += 1
            return self._inner.generate_text(
                messages, temperature=temperature, max_tokens=max_tokens
            )

        def generate_structured(
            self, messages, *, schema, temperature=None, max_tokens=None
        ):
            self.generate_calls += 1
            return self._inner.generate_structured(
                messages,
                schema=schema,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        def generate_with_tools(self, messages, tools, **kwargs):
            self.generate_calls += 1
            return self._inner.generate_with_tools(messages, tools, **kwargs)

    db = SessionLocal()
    errors: list[str] = []
    try:
        user = (
            db.query(User)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .join(RolePermission, RolePermission.role_id == Role.id)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .filter(
                Permission.name == COMPANY_DOCUMENTS_READ,
                User.is_active.is_(True),
            )
            .order_by(User.id.asc())
            .first()
        )
        if user is None:
            raise RuntimeError("No user with company_documents:read found")

        role_names: set[str] = set()
        permission_names: set[str] = set()
        for user_role in user.user_roles:
            role = user_role.role
            if role is None:
                continue
            role_names.add(role.name)
            for role_perm in role.role_permissions:
                if role_perm.permission is not None:
                    permission_names.add(role_perm.permission.name)

        context = AIExecutionContext(
            user_id=user.id,
            role_names=frozenset(role_names),
            permission_names=frozenset(permission_names),
            employee_id=None,
            candidate_id=None,
        )

        embed_provider = _CountingEmbeddingProvider(get_embedding_provider())
        llm_provider = _CountingLLMProvider(get_llm_provider())
        query_service = RAGQueryService(
            embedding_service=EmbeddingService(db, embed_provider),
            hybrid_service=HybridRetrievalService(db),
            db=db,
        )
        generation_service = GroundedGenerationService(
            llm_provider=llm_provider,
            db=db,
        )

        query_result = query_service.query(
            RAGQueryRequest(query=query, context=context)
        )
        answer = generation_service.generate(
            RAGGenerationRequest(query_result=query_result, context=context)
        )

        ranked_docs = [hit.company_document_id for hit in query_result.results]
        metrics = compute_retrieval_metrics([2], ranked_docs)
        retrieval_metrics = RetrievalMetrics(**metrics)

        citation_checks = evaluate_citations(
            answer_text=answer.answer,
            citations=answer.citations,
            context_items=query_result.context,
        )
        generation_checks = evaluate_generation(
            answer_text=answer.answer,
            should_abstain=False,
            expected_facts=["AI Software Engineer"],
            citation_checks=citation_checks,
        )

        if embed_provider.embed_calls != 1:
            errors.append(
                f"expected 1 embed call, got {embed_provider.embed_calls}"
            )
        if llm_provider.generate_calls != 1:
            errors.append(
                f"expected 1 generate call, got {llm_provider.generate_calls}"
            )
        if not query_result.has_context:
            errors.append("expected retrieval context for document 2")
        if 2 not in ranked_docs:
            errors.append("expected document id 2 in retrieval results")
        if not answer.citations:
            errors.append("expected at least one citation")
        elif any(c.company_document_id != 2 for c in answer.citations):
            errors.append("expected all citations to document id 2")
        elif any(c.page_start != 1 for c in answer.citations):
            errors.append("expected citation page_start=1 for doc 2 smoke PDF")
        if answer.embedding_model != rag_settings.rag_embedding_model:
            errors.append("embedding model mismatch")

        passed = (
            not errors
            and generation_checks.passed
            and citation_checks.passed
            and (retrieval_metrics.recall_at_1 or 0) >= 1.0
        )

        live_result = EvaluationResult(
            case_id="internship_position_live",
            passed=passed,
            retrieval_metrics=retrieval_metrics,
            citation_checks=citation_checks,
            generation_checks=generation_checks,
            errors=errors
            + generation_checks.details
            + citation_checks.details,
        )
        offline = run_offline()
        return aggregate_summary(
            offline.results + [live_result],
            gemini_embed_calls=embed_provider.embed_calls,
            gemini_generate_calls=llm_provider.generate_calls,
        )
    finally:
        db.close()


def format_report(summary: EvaluationSummary) -> str:
    def fmt(value: float | None) -> str:
        return "n/a" if value is None else f"{value:.3f}"

    security = summary.results
    sec = next((r.security_checks for r in security if r.security_checks), None)

    lines = [
        "RAG Evaluation",
        "==============",
        "",
        f"Cases: {summary.total_cases}",
        f"Passed: {summary.passed_cases}",
        f"Failed: {summary.failed_cases}",
        "",
        "Retrieval",
        "---------",
        f"Recall@1: {fmt(summary.recall_at_1)}",
        f"Recall@3: {fmt(summary.recall_at_3)}",
        f"Recall@5: {fmt(summary.recall_at_5)}",
        f"Precision@1: {fmt(summary.precision_at_1)}",
        f"Precision@3: {fmt(summary.precision_at_3)}",
        f"Precision@5: {fmt(summary.precision_at_5)}",
        f"MRR: {fmt(summary.mrr)}",
        "",
        "Generation",
        "----------",
        f"Citation validity: {fmt(summary.citation_validity_rate)}",
        f"Abstention accuracy: {fmt(summary.abstention_accuracy)}",
        "",
        "Security",
        "--------",
    ]
    if sec is None:
        lines.append("Access control: n/a")
    else:
        lines.extend(
            [
                f"Access control: {'PASS' if sec.unauthorized_excluded else 'FAIL'}",
                f"Archived document filtering: {'PASS' if sec.employee_archived_filtered and sec.hr_can_access_archived else 'FAIL'}",
                f"Private document isolation: {'PASS' if sec.private_docs_isolated else 'FAIL'}",
                f"Candidate CV isolation: {'PASS' if sec.candidate_cvs_isolated else 'FAIL'}",
                f"Prompt injection handling: {'PASS' if sec.prompt_injection_structure_ok else 'FAIL'}",
            ]
        )

    lines.append("")
    if summary.gemini_embed_calls == 0 and summary.gemini_generate_calls == 0:
        lines.append("No Gemini calls performed.")
    else:
        lines.append(
            f"Gemini embed calls: {summary.gemini_embed_calls}; "
            f"generate calls: {summary.gemini_generate_calls}"
        )

    failed = [r for r in summary.results if not r.passed]
    if failed:
        lines.append("")
        lines.append("Failed cases")
        lines.append("------------")
        for result in failed:
            err = "; ".join(result.errors) if result.errors else "failed"
            lines.append(f"- {result.case_id}: {err}")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 5.10 RAG evaluation runner")
    parser.add_argument(
        "--live-generation",
        action="store_true",
        help="Opt-in: run one live Knowledge Agent evaluation (uses Gemini)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print EvaluationSummary as JSON",
    )
    args = parser.parse_args(argv)

    if args.live_generation:
        summary = run_live_generation()
    else:
        summary = run_offline()

    if args.json:
        print(summary.model_dump_json(indent=2))
    else:
        print(format_report(summary))

    return 0 if summary.failed_cases == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
