"""RAG grounded generation (Phase 5.8) — authorized context → answer + citations."""

from app.ai.rag.generation.citations import (
    CitationSource,
    build_registry,
    extract_citation_ids,
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
    Citation,
    GenerationUsage,
    RAGAnswer,
    RAGGenerationRequest,
)
from app.ai.rag.generation.service import (
    NO_CONTEXT_ABSTENTION,
    GroundedGenerationService,
)

__all__ = [
    "ANSWER_JSON_SCHEMA",
    "Citation",
    "CitationSource",
    "GROUNDED_SYSTEM_PROMPT",
    "GenerationUsage",
    "GroundedGenerationService",
    "NO_CONTEXT_ABSTENTION",
    "RAGAnswer",
    "RAGGenerationError",
    "RAGGenerationRequest",
    "RAGGenerationValidationError",
    "build_registry",
    "build_user_message",
    "extract_citation_ids",
    "sanitize_answer_and_citations",
    "sources_from_context",
]
