"""RAG query pipeline: validate → embed → hybrid retrieve → assemble context."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.rag.config import rag_settings
from app.ai.rag.embeddings.exceptions import (
    EmbeddingException,
    EmbeddingProviderError,
    EmbeddingValidationError,
)
from app.ai.rag.embeddings.service import EmbeddingService
from app.ai.rag.query.context import ContextAssembler
from app.ai.rag.query.exceptions import RAGQueryError, RAGQueryValidationError
from app.ai.rag.query.schemas import RAGQueryRequest, RAGQueryResult
from app.ai.rag.retrieval.exceptions import RetrievalError, RetrievalValidationError
from app.ai.rag.retrieval.hybrid import HybridRetrievalService
from app.ai.rag.retrieval.schemas import HybridRequest


class RAGQueryService:
    """Connect query embedding to secure hybrid retrieval and context assembly.

    Does not call conversational Gemini / answer generation.
    """

    def __init__(
        self,
        *,
        embedding_service: EmbeddingService,
        hybrid_service: HybridRetrievalService,
        assembler: ContextAssembler | None = None,
        query_max_characters: int | None = None,
        default_top_k: int | None = None,
        max_top_k: int | None = None,
        embedding_model: str | None = None,
        embedding_dimensions: int | None = None,
        db: Session | None = None,
    ) -> None:
        self.db = db
        self._embedding = embedding_service
        self._hybrid = hybrid_service
        self._assembler = assembler or ContextAssembler()
        self._query_max_characters = (
            rag_settings.rag_query_max_characters
            if query_max_characters is None
            else query_max_characters
        )
        self._default_top_k = (
            rag_settings.rag_retrieval_top_k if default_top_k is None else default_top_k
        )
        self._max_top_k = (
            rag_settings.rag_retrieval_max_top_k if max_top_k is None else max_top_k
        )
        self._embedding_model = embedding_model or rag_settings.rag_embedding_model
        self._embedding_dimensions = (
            embedding_dimensions
            if embedding_dimensions is not None
            else rag_settings.rag_embedding_dimensions
        )

    def query(self, request: RAGQueryRequest) -> RAGQueryResult:
        cleaned = self._validate_query(request.query)
        top_k = self._resolve_top_k(request.top_k)

        try:
            embed_result = self._embedding.embed_query(cleaned)
        except EmbeddingValidationError as exc:
            raise RAGQueryValidationError(str(exc)) from exc
        except EmbeddingProviderError as exc:
            raise RAGQueryError("Query embedding failed") from exc
        except EmbeddingException as exc:
            raise RAGQueryError("Query embedding failed") from exc

        try:
            hits = self._hybrid.retrieve(
                HybridRequest(
                    query_text=cleaned,
                    query_embedding=list(embed_result.vector),
                    context=request.context,
                    top_k=top_k,
                )
            )
        except RetrievalValidationError as exc:
            raise RAGQueryValidationError(str(exc)) from exc
        except RetrievalError as exc:
            raise RAGQueryError("Hybrid retrieval failed") from exc

        context = self._assembler.assemble(hits)
        return RAGQueryResult(
            query=cleaned,
            retrieval_count=len(hits),
            selected_context_count=len(context),
            has_context=bool(context),
            results=hits,
            context=context,
            embedding_model=embed_result.model or self._embedding_model,
            embedding_dimensions=embed_result.dimensions or self._embedding_dimensions,
        )

    def _validate_query(self, query: str) -> str:
        cleaned = (query or "").strip()
        if not cleaned:
            raise RAGQueryValidationError("Query must not be empty")
        if len(cleaned) > self._query_max_characters:
            raise RAGQueryValidationError(
                f"Query exceeds max length of {self._query_max_characters} characters"
            )
        return cleaned

    def _resolve_top_k(self, top_k: int | None) -> int:
        value = self._default_top_k if top_k is None else top_k
        if value < 1:
            raise RAGQueryValidationError("top_k must be >= 1")
        if value > self._max_top_k:
            raise RAGQueryValidationError(
                f"top_k must be <= {self._max_top_k} (got {value})"
            )
        return value
