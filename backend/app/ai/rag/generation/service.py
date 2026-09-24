"""Grounded generation: authorized RAG context → conversational LLM → citations."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.core.exceptions import LLMProviderError
from app.ai.core.llm import get_llm_provider
from app.ai.core.llm.base import LLMMessage, LLMProvider, LLMUsage
from app.ai.rag.config import rag_settings
from app.ai.rag.generation.citations import (
    build_registry,
    sanitize_answer_and_citations,
)
from app.ai.rag.generation.exceptions import (
    RAGGenerationError,
    RAGGenerationValidationError,
)
from app.ai.rag.generation.prompts import (
    ANSWER_JSON_SCHEMA,
    GROUNDED_SYSTEM_PROMPT,
    build_user_message,
    sources_from_context,
)
from app.ai.rag.generation.schemas import (
    GenerationUsage,
    RAGAnswer,
    RAGGenerationRequest,
)

NO_CONTEXT_ABSTENTION = (
    "I don't have enough information in the available company documents "
    "to answer that question."
)


class GroundedGenerationService:
    """Answer only from Phase 5.7 authorized RAGQueryResult context."""

    def __init__(
        self,
        *,
        llm_provider: LLMProvider | None = None,
        db: Session | None = None,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
        system_prompt: str | None = None,
    ) -> None:
        self.db = db
        self._llm = llm_provider if llm_provider is not None else get_llm_provider()
        self._max_output_tokens = (
            rag_settings.rag_generation_max_output_tokens
            if max_output_tokens is None
            else max_output_tokens
        )
        self._temperature = (
            rag_settings.rag_generation_temperature
            if temperature is None
            else temperature
        )
        self._system_prompt = system_prompt or GROUNDED_SYSTEM_PROMPT

    def generate(self, request: RAGGenerationRequest) -> RAGAnswer:
        result = request.query_result
        query = result.query

        if not result.has_context or not result.context:
            return RAGAnswer(
                query=query,
                answer=NO_CONTEXT_ABSTENTION,
                citations=[],
                has_context=False,
                retrieval_count=result.retrieval_count,
                selected_context_count=result.selected_context_count,
                model="",
                usage=None,
                embedding_model=result.embedding_model,
                embedding_dimensions=result.embedding_dimensions,
            )

        titles = self._load_document_titles(
            [item.company_document_id for item in result.context]
        )
        sources = sources_from_context(result.context, document_titles=titles)
        registry = build_registry(sources)
        user_message = build_user_message(query, sources)
        messages = [
            LLMMessage(role="system", content=self._system_prompt),
            LLMMessage(role="user", content=user_message),
        ]

        try:
            response = self._llm.generate_structured(
                messages,
                schema=ANSWER_JSON_SCHEMA,
                temperature=self._temperature,
                max_tokens=self._max_output_tokens,
            )
        except LLMProviderError as exc:
            raise RAGGenerationError("Grounded generation failed") from exc

        raw_answer = response.data.get("answer") if isinstance(response.data, dict) else None
        if not isinstance(raw_answer, str) or not raw_answer.strip():
            raise RAGGenerationValidationError("Model returned an empty answer")

        answer, citations = sanitize_answer_and_citations(raw_answer, registry)
        if not answer.strip():
            raise RAGGenerationValidationError("Model returned an empty answer")

        return RAGAnswer(
            query=query,
            answer=answer,
            citations=citations,
            has_context=True,
            retrieval_count=result.retrieval_count,
            selected_context_count=result.selected_context_count,
            model=response.model or "",
            usage=_map_usage(response.usage),
            embedding_model=result.embedding_model,
            embedding_dimensions=result.embedding_dimensions,
        )

    def _load_document_titles(self, document_ids: list[int]) -> dict[int, str]:
        unique_ids = sorted({doc_id for doc_id in document_ids if doc_id})
        if not unique_ids or self.db is None:
            return {}
        from app.modules.documents.models import CompanyDocument

        rows = (
            self.db.query(CompanyDocument.id, CompanyDocument.title)
            .filter(CompanyDocument.id.in_(unique_ids))
            .all()
        )
        return {int(row.id): str(row.title) for row in rows}


def _map_usage(usage: LLMUsage | None) -> GenerationUsage | None:
    if usage is None:
        return None
    return GenerationUsage(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        thinking_tokens=usage.thinking_tokens,
        total_tokens=usage.total_tokens,
    )
