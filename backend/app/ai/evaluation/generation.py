"""Deterministic citation and generation checks (no LLM judge)."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.ai.core.context.models import AIExecutionContext
from app.ai.evaluation.schemas import (
    CitationChecks,
    FixtureCitation,
    FixtureContextItem,
    GenerationChecks,
)
from app.ai.rag.generation.citations import extract_citation_ids
from app.ai.rag.generation.schemas import Citation, RAGGenerationRequest
from app.ai.rag.generation.service import NO_CONTEXT_ABSTENTION, GroundedGenerationService
from app.ai.rag.query.schemas import RAGContextItem, RAGQueryResult


def _context_registry(
    context_items: list[RAGContextItem] | list[FixtureContextItem],
) -> dict[int, RAGContextItem | FixtureContextItem]:
    return {index: item for index, item in enumerate(context_items, start=1)}


def evaluate_citations(
    *,
    answer_text: str,
    citations: list[Citation] | list[FixtureCitation],
    context_items: list[RAGContextItem] | list[FixtureContextItem],
    expected_invalid_ids: list[int] | None = None,
) -> CitationChecks:
    """Validate citation integrity against retrieved/fixture context."""
    details: list[str] = []
    registry = _context_registry(context_items)
    marker_ids = extract_citation_ids(answer_text)
    invalid_from_markers = [cid for cid in marker_ids if cid not in registry]

    all_ids_valid = True
    matches_context = True

    for citation in citations:
        cid = citation.citation_id
        if cid not in registry:
            all_ids_valid = False
            details.append(f"citation_id {cid} not in context registry")
            continue
        item = registry[cid]
        if citation.chunk_id != item.chunk_id:
            matches_context = False
            details.append(
                f"citation {cid} chunk_id mismatch: "
                f"{citation.chunk_id} != {item.chunk_id}"
            )
        if citation.company_document_id != item.company_document_id:
            matches_context = False
            details.append(
                f"citation {cid} document_id mismatch: "
                f"{citation.company_document_id} != {item.company_document_id}"
            )
        if (
            citation.page_start != item.page_start
            or citation.page_end != item.page_end
        ):
            matches_context = False
            details.append(
                f"citation {cid} page mismatch: "
                f"{citation.page_start}-{citation.page_end} != "
                f"{item.page_start}-{item.page_end}"
            )

    if invalid_from_markers:
        all_ids_valid = False
        details.append(f"invalid markers in answer: {invalid_from_markers}")

    citation_less = len(citations) == 0 and len(marker_ids) == 0

    if expected_invalid_ids is not None:
        expected_set = set(expected_invalid_ids)
        found_set = set(invalid_from_markers)
        passed = expected_set.issubset(found_set) and bool(found_set)
        if passed:
            details.append("invalid citation ids detected as expected")
        else:
            details.append(
                f"expected invalid ids {sorted(expected_set)}, "
                f"found markers {sorted(found_set)}"
            )
    else:
        passed = all_ids_valid and matches_context and not invalid_from_markers

    return CitationChecks(
        all_citation_ids_valid=all_ids_valid and not invalid_from_markers,
        citations_match_context=matches_context,
        invalid_citation_ids=invalid_from_markers,
        citation_less=citation_less,
        passed=passed,
        details=details,
    )


def evaluate_generation(
    *,
    answer_text: str,
    should_abstain: bool,
    expected_facts: list[str] | None = None,
    citation_checks: CitationChecks | None = None,
    llm_not_called: bool | None = None,
    expect_invalid_citations: bool = False,
) -> GenerationChecks:
    details: list[str] = []
    non_empty = bool((answer_text or "").strip())
    abstained = answer_text.strip() == NO_CONTEXT_ABSTENTION
    abstained_ok = abstained if should_abstain else not abstained

    if should_abstain and not abstained:
        details.append("expected abstention response")
    if not should_abstain and abstained:
        details.append("unexpected abstention")

    facts_ok = True
    if expected_facts and not should_abstain:
        missing = [fact for fact in expected_facts if fact not in answer_text]
        facts_ok = not missing
        if missing:
            details.append(f"missing expected facts: {missing}")

    unsupported = False
    if citation_checks is not None and not should_abstain and not expect_invalid_citations:
        unsupported = bool(citation_checks.invalid_citation_ids)

    llm_ok = True
    if should_abstain and llm_not_called is not None:
        llm_ok = llm_not_called
        if not llm_ok:
            details.append("LLM was called on abstention path")

    answer_ok = (non_empty and not should_abstain) or (should_abstain and abstained)
    citation_ok = True
    if citation_checks is not None and not expect_invalid_citations:
        citation_ok = citation_checks.passed or (
            should_abstain and citation_checks.citation_less
        )

    passed = answer_ok and abstained_ok and facts_ok and not unsupported and llm_ok
    if citation_checks is not None and expect_invalid_citations:
        passed = passed and citation_checks.passed
    elif citation_checks is not None:
        passed = passed and citation_ok

    return GenerationChecks(
        answer_non_empty=non_empty,
        abstained_as_expected=abstained_ok,
        facts_present=facts_ok,
        unsupported_citations=unsupported,
        llm_not_called_on_abstention=llm_not_called,
        passed=passed,
        details=details,
    )


def evaluate_abstention_offline() -> tuple[GenerationChecks, CitationChecks]:
    """Run real GroundedGenerationService with empty context; LLM must not be called."""
    llm = MagicMock()
    service = GroundedGenerationService(llm_provider=llm)
    ctx = AIExecutionContext(
        user_id=1,
        role_names=frozenset({"employee"}),
        permission_names=frozenset({"company_documents:read"}),
        employee_id=1,
        candidate_id=None,
    )
    query_result = RAGQueryResult(
        query="What is the secret bonus policy for 2099?",
        retrieval_count=0,
        selected_context_count=0,
        has_context=False,
        results=[],
        context=[],
        embedding_model="gemini-embedding-2",
        embedding_dimensions=768,
    )
    answer = service.generate(
        RAGGenerationRequest(query_result=query_result, context=ctx)
    )
    llm_not_called = (
        not llm.generate_structured.called and not llm.generate_text.called
    )
    cite = CitationChecks(
        all_citation_ids_valid=True,
        citations_match_context=True,
        invalid_citation_ids=[],
        citation_less=answer.citations == [],
        passed=(
            answer.citations == [] and answer.answer == NO_CONTEXT_ABSTENTION
        ),
        details=(
            ["abstention has no citations"]
            if answer.citations == []
            else ["abstention unexpectedly produced citations"]
        ),
    )
    gen = evaluate_generation(
        answer_text=answer.answer,
        should_abstain=True,
        citation_checks=cite,
        llm_not_called=llm_not_called,
    )
    return gen, cite


def to_rag_context_items(
    fixtures: list[FixtureContextItem],
) -> list[RAGContextItem]:
    return [
        RAGContextItem(
            chunk_id=item.chunk_id,
            company_document_id=item.company_document_id,
            content=item.content,
            page_start=item.page_start,
            page_end=item.page_end,
            chunk_index=item.chunk_index,
            content_hash=item.content_hash,
            metadata=dict(item.metadata),
            rrf_score=item.rrf_score,
        )
        for item in fixtures
    ]
