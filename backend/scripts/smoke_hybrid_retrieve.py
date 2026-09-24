"""Smoke: hybrid vector + FTS retrieval using stored embedding (NO Gemini).

Run from backend/ after Phase 5.4 embedded DOCUMENT_ID:

  $env:PYTHONPATH = "."
  python scripts/smoke_hybrid_retrieve.py
"""

from app.modules.identity import models as identity_models  # noqa: F401
from app.modules.employees import models as employee_models  # noqa: F401
from app.modules.documents import models as document_models  # noqa: F401
from app.ai.rag import models as rag_models  # noqa: F401

from app.ai.core.context.models import AIExecutionContext
from app.ai.rag.chunking import KnowledgeChunkRepository
from app.ai.rag.config import rag_settings
from app.ai.rag.retrieval import COMPANY_DOCUMENTS_READ, HybridRetrievalService
from app.ai.rag.retrieval.schemas import HybridRequest
from app.core.database import SessionLocal
from app.modules.identity.models import Permission, Role, RolePermission, User, UserRole

DOCUMENT_ID = 2
QUERY_TEXT = "Casablanca"


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


db = SessionLocal()
try:
    chunks = KnowledgeChunkRepository(db).list_by_company_document_id(DOCUMENT_ID)
    assert chunks, f"No chunks for document {DOCUMENT_ID}"
    source = next((c for c in chunks if c.embedding is not None), None)
    assert source is not None, "No embedded chunk — run smoke_embed_chunks.py first"

    query_embedding = list(source.embedding)
    context = _context_with_company_read(db)

    print("query:", QUERY_TEXT)
    print("document_id:", DOCUMENT_ID)
    print("top_k:", rag_settings.rag_retrieval_top_k)

    service = HybridRetrievalService(db)
    hits = service.retrieve(
        HybridRequest(
            query_text=QUERY_TEXT,
            query_embedding=query_embedding,
            context=context,
            top_k=rag_settings.rag_retrieval_top_k,
        )
    )
    debug = service.last_debug
    assert debug is not None
    print("vector_candidate_count:", debug.vector_candidate_count)
    print("fts_candidate_count:", debug.fts_candidate_count)
    print("final_result_count:", len(hits))
    assert hits, "expected at least one hybrid hit"
    top = hits[0]
    print("chunk_id:", top.chunk_id)
    print("company_document_id:", top.company_document_id)
    print(
        "vector_similarity:",
        None if top.vector_similarity is None else round(top.vector_similarity, 6),
    )
    print("fts_rank:", None if top.fts_rank is None else round(top.fts_rank, 6))
    print("rrf_score:", round(top.rrf_score, 6))
    print("page_range:", f"{top.page_start}-{top.page_end}")
    print("content_preview:", top.content[:80].replace("\n", " "))
    assert top.company_document_id == DOCUMENT_ID
    print("smoke_hybrid_ok: True")
finally:
    db.close()
