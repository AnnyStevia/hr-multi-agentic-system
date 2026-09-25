"""Knowledge Agent — thin orchestrator over RAG query + grounded generation."""

from __future__ import annotations

from app.ai.agents.knowledge.exceptions import (
    KnowledgeAgentError,
    KnowledgeAgentValidationError,
)
from app.ai.agents.knowledge.schemas import KnowledgeAgentRequest
from app.ai.rag.generation.exceptions import (
    RAGGenerationError,
    RAGGenerationValidationError,
)
from app.ai.rag.generation.schemas import RAGAnswer, RAGGenerationRequest
from app.ai.rag.generation.service import GroundedGenerationService
from app.ai.rag.query.exceptions import RAGQueryError, RAGQueryValidationError
from app.ai.rag.query.schemas import RAGQueryRequest
from app.ai.rag.query.service import RAGQueryService


class KnowledgeAgent:
    """Read-only company-knowledge assistant.

    Does not call Gemini, repositories, or tools directly. Authorization and
    grounding remain inside the existing RAG pipeline.
    """

    def __init__(
        self,
        *,
        query_service: RAGQueryService,
        generation_service: GroundedGenerationService,
    ) -> None:
        self._query = query_service
        self._generation = generation_service

    def ask(self, request: KnowledgeAgentRequest) -> RAGAnswer:
        question = (request.question or "").strip()
        if not question:
            raise KnowledgeAgentValidationError("Question must not be empty")

        try:
            query_result = self._query.query(
                RAGQueryRequest(
                    query=question,
                    context=request.context,
                    top_k=request.top_k,
                )
            )
        except RAGQueryValidationError as exc:
            raise KnowledgeAgentValidationError(str(exc)) from exc
        except RAGQueryError as exc:
            raise KnowledgeAgentError("Knowledge query failed") from exc

        try:
            return self._generation.generate(
                RAGGenerationRequest(
                    query_result=query_result,
                    context=request.context,
                )
            )
        except RAGGenerationValidationError as exc:
            raise KnowledgeAgentValidationError(str(exc)) from exc
        except RAGGenerationError as exc:
            raise KnowledgeAgentError("Knowledge generation failed") from exc
