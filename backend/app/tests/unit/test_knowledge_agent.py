"""Unit tests for KnowledgeAgent (mocked RAG services; no Gemini)."""

from unittest.mock import MagicMock

import pytest

from app.ai.agents.knowledge import (
    KnowledgeAgent,
    KnowledgeAgentError,
    KnowledgeAgentRequest,
    KnowledgeAgentValidationError,
)
from app.ai.core.context.models import AIExecutionContext
from app.ai.rag.generation import NO_CONTEXT_ABSTENTION
from app.ai.rag.generation.exceptions import RAGGenerationError
from app.ai.rag.generation.schemas import Citation, RAGAnswer
from app.ai.rag.query.exceptions import RAGQueryError
from app.ai.rag.query.schemas import RAGQueryResult
from app.ai.rag.retrieval.filters import COMPANY_DOCUMENTS_READ


def _ctx() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=7,
        role_names=frozenset({"employee"}),
        permission_names=frozenset({COMPANY_DOCUMENTS_READ}),
        employee_id=3,
        candidate_id=None,
    )


def _query_result(*, has_context: bool = True) -> RAGQueryResult:
    return RAGQueryResult(
        query="What position?",
        retrieval_count=1 if has_context else 0,
        selected_context_count=1 if has_context else 0,
        has_context=has_context,
        results=[],
        context=[],
        embedding_model="gemini-embedding-2",
        embedding_dimensions=768,
    )


def test_ask_empty_question_rejects_without_calling_services():
    query = MagicMock()
    generation = MagicMock()
    agent = KnowledgeAgent(query_service=query, generation_service=generation)
    with pytest.raises(KnowledgeAgentValidationError, match="empty"):
        agent.ask(KnowledgeAgentRequest(question="   ", context=_ctx()))
    query.query.assert_not_called()
    generation.generate.assert_not_called()


def test_ask_grounds_via_query_then_generation():
    ctx = _ctx()
    query_result = _query_result(has_context=True)
    query = MagicMock()
    query.query.return_value = query_result
    generation = MagicMock()
    generation.generate.return_value = RAGAnswer(
        query="What position?",
        answer="AI Software Engineer [1]",
        citations=[
            Citation(
                citation_id=1,
                chunk_id=6,
                company_document_id=2,
                page_start=1,
                page_end=1,
                document_name="CV",
                content_hash="a" * 64,
            )
        ],
        has_context=True,
        retrieval_count=1,
        selected_context_count=1,
        model="gemini-3.8-flash",
        embedding_model="gemini-embedding-2",
        embedding_dimensions=768,
    )
    agent = KnowledgeAgent(query_service=query, generation_service=generation)

    answer = agent.ask(
        KnowledgeAgentRequest(question="  What position?  ", context=ctx, top_k=3)
    )

    query.query.assert_called_once()
    query_req = query.query.call_args.args[0]
    assert query_req.query == "What position?"
    assert query_req.context is ctx
    assert query_req.top_k == 3

    generation.generate.assert_called_once()
    gen_req = generation.generate.call_args.args[0]
    assert gen_req.query_result is query_result
    assert gen_req.context is ctx

    assert answer.answer == "AI Software Engineer [1]"
    assert answer.citations[0].company_document_id == 2
    assert answer.has_context is True


def test_ask_no_context_returns_generation_abstention():
    ctx = _ctx()
    query_result = _query_result(has_context=False)
    query = MagicMock()
    query.query.return_value = query_result
    generation = MagicMock()
    generation.generate.return_value = RAGAnswer(
        query="Anything?",
        answer=NO_CONTEXT_ABSTENTION,
        citations=[],
        has_context=False,
        retrieval_count=0,
        selected_context_count=0,
        model="",
        embedding_model="gemini-embedding-2",
        embedding_dimensions=768,
    )
    agent = KnowledgeAgent(query_service=query, generation_service=generation)
    answer = agent.ask(KnowledgeAgentRequest(question="Anything?", context=ctx))
    assert answer.has_context is False
    assert answer.answer == NO_CONTEXT_ABSTENTION
    assert answer.citations == []
    generation.generate.assert_called_once()


def test_query_failure_wrapped():
    query = MagicMock()
    query.query.side_effect = RAGQueryError("embed failed")
    generation = MagicMock()
    agent = KnowledgeAgent(query_service=query, generation_service=generation)
    with pytest.raises(KnowledgeAgentError, match="Knowledge query failed"):
        agent.ask(KnowledgeAgentRequest(question="hi", context=_ctx()))
    generation.generate.assert_not_called()


def test_generation_failure_wrapped():
    query = MagicMock()
    query.query.return_value = _query_result()
    generation = MagicMock()
    generation.generate.side_effect = RAGGenerationError("llm down")
    agent = KnowledgeAgent(query_service=query, generation_service=generation)
    with pytest.raises(KnowledgeAgentError, match="Knowledge generation failed"):
        agent.ask(KnowledgeAgentRequest(question="hi", context=_ctx()))
