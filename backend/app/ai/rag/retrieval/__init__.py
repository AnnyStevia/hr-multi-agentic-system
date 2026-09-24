"""Secure pgvector cosine retrieval + hybrid FTS/RRF (Phases 5.5–5.6)."""

from app.ai.rag.retrieval.exceptions import (
    RetrievalAuthorizationError,
    RetrievalError,
    RetrievalValidationError,
)
from app.ai.rag.retrieval.filters import (
    COMPANY_DOCUMENTS_READ,
    is_hr_staff,
    require_company_documents_read,
)
from app.ai.rag.retrieval.fts_repository import (
    FtsRetrievalRow,
    FullTextRetrievalRepository,
)
from app.ai.rag.retrieval.hybrid import HybridRetrievalService
from app.ai.rag.retrieval.repository import RetrievalRow, VectorRetrievalRepository
from app.ai.rag.retrieval.rrf import fuse_rankings
from app.ai.rag.retrieval.schemas import (
    HybridRequest,
    HybridRetrievalHit,
    RetrievalHit,
    RetrievalRequest,
)
from app.ai.rag.retrieval.service import RetrievalService

__all__ = [
    "COMPANY_DOCUMENTS_READ",
    "FullTextRetrievalRepository",
    "FtsRetrievalRow",
    "HybridRequest",
    "HybridRetrievalHit",
    "HybridRetrievalService",
    "RetrievalAuthorizationError",
    "RetrievalError",
    "RetrievalHit",
    "RetrievalRequest",
    "RetrievalRow",
    "RetrievalService",
    "RetrievalValidationError",
    "VectorRetrievalRepository",
    "fuse_rankings",
    "is_hr_staff",
    "require_company_documents_read",
]
