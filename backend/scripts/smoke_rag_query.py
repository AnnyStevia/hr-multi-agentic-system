"""Smoke: RAG query pipeline (ONE Gemini query embedding; no generation).

Run from backend/ after doc 2 is chunked+embedded:

  $env:PYTHONPATH = "."
  python scripts/smoke_rag_query.py
"""

from app.modules.identity import models as identity_models  # noqa: F401
from app.modules.employees import models as employee_models  # noqa: F401
from app.modules.documents import models as document_models  # noqa: F401
from app.ai.rag import models as rag_models  # noqa: F401

from app.ai.core.context.models import AIExecutionContext
from app.ai.rag.config import rag_settings
from app.ai.rag.embeddings import EmbeddingService, get_embedding_provider
from app.ai.rag.query import RAGQueryRequest, RAGQueryService
from app.ai.rag.retrieval import COMPANY_DOCUMENTS_READ, HybridRetrievalService
from app.core.database import SessionLocal
from app.modules.identity.models import Permission, Role, RolePermission, User, UserRole

QUERY = "Casablanca"


def _context_with_company_read(db) -> AIExecutionContext:
    user = (
        db.query(User)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .join(RolePermission, RolePermission.role_id == Role.id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .filter(Permission.name == COMPANY_DOCUMENTS_READ, User.is_active.is_(True))
        .order_by(User.id.asc())
        .first()
    )
    assert user is not None, "No user with company_documents:read found"
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
    return AIExecutionContext(
        user_id=user.id,
        role_names=frozenset(role_names),
        permission_names=frozenset(permission_names),
        employee_id=None,
        candidate_id=None,
    )


class _CountingProvider:
    """Wrap embedding provider to assert exactly one Gemini embed call."""

    def __init__(self, inner):
        self._inner = inner
        self.embed_calls = 0

    def embed_text(self, text: str, *, task_type: str | None = None):
        self.embed_calls += 1
        return self._inner.embed_text(text, task_type=task_type)

    def embed_texts(self, texts, *, task_type: str | None = None):
        self.embed_calls += len(list(texts))
        return self._inner.embed_texts(texts, task_type=task_type)


db = SessionLocal()
try:
    context = _context_with_company_read(db)
    provider = _CountingProvider(get_embedding_provider())
    embedding_service = EmbeddingService(db, provider)
    hybrid = HybridRetrievalService(db)
    service = RAGQueryService(
        embedding_service=embedding_service,
        hybrid_service=hybrid,
        db=db,
    )

    print("query:", QUERY)
    # No conversational / generateContent path — query pipeline only.
    result = service.query(RAGQueryRequest(query=QUERY, context=context))

    print("gemini_embed_calls:", provider.embed_calls)
    assert provider.embed_calls == 1, "expected exactly one query embedding call"

    print("retrieval_count:", result.retrieval_count)
    print("selected_context_count:", result.selected_context_count)
    print("has_context:", result.has_context)
    print("embedding_model:", result.embedding_model)
    print("query_embedding_dimensions:", result.embedding_dimensions)
    assert result.embedding_dimensions == rag_settings.rag_embedding_dimensions
    assert result.embedding_model == rag_settings.rag_embedding_model

    for item in result.context:
        print(
            f"chunk_id={item.chunk_id} doc={item.company_document_id} "
            f"rrf={round(item.rrf_score, 6)} pages={item.page_start}-{item.page_end}"
        )
        print("preview:", item.content[:80].replace("\n", " "))

    assert result.has_context, "expected context from document library (doc 2 indexed)"
    print("smoke_rag_query_ok: True")
finally:
    db.close()
