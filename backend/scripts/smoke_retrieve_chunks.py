"""Smoke: secure vector retrieval using a stored embedding (NO Gemini).

Run from backend/ after Phase 5.4 embedded DOCUMENT_ID:

  $env:PYTHONPATH = "."
  python scripts/smoke_retrieve_chunks.py
"""

from app.modules.identity import models as identity_models  # noqa: F401
from app.modules.employees import models as employee_models  # noqa: F401
from app.modules.documents import models as document_models  # noqa: F401
from app.ai.rag import models as rag_models  # noqa: F401

from app.ai.core.context.models import AIExecutionContext
from app.ai.rag.chunking import KnowledgeChunkRepository
from app.ai.rag.config import rag_settings
from app.ai.rag.retrieval import COMPANY_DOCUMENTS_READ, RetrievalService
from app.ai.rag.retrieval.schemas import RetrievalRequest
from app.core.database import SessionLocal
from app.modules.identity.models import Permission, Role, RolePermission, User, UserRole

DOCUMENT_ID = 2


def _context_with_company_read(db) -> AIExecutionContext:
    """Build AIExecutionContext from a DB user that has company_documents:read."""
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
    assert chunks, f"No chunks for document {DOCUMENT_ID} — run ingest+chunk+embed first"
    source = next((c for c in chunks if c.embedding is not None), None)
    assert source is not None, "No embedded chunk found — run smoke_embed_chunks.py first"

    query = list(source.embedding)
    assert len(query) == rag_settings.rag_embedding_dimensions

    context = _context_with_company_read(db)
    print("document_id:", DOCUMENT_ID)
    print("source_chunk_id:", source.id)
    print("top_k:", rag_settings.rag_retrieval_top_k)
    print("context_user_id:", context.user_id)
    print("context_roles:", sorted(context.role_names))

    hits = RetrievalService(db).retrieve(
        RetrievalRequest(
            query_embedding=query,
            context=context,
            top_k=rag_settings.rag_retrieval_top_k,
        )
    )
    print("result_count:", len(hits))
    assert hits, "expected at least one hit"
    top = hits[0]
    print("chunk_id:", top.chunk_id)
    print("company_document_id:", top.company_document_id)
    print("similarity:", round(top.similarity, 6))
    print("page_range:", f"{top.page_start}-{top.page_end}")
    preview = top.content[:80].replace("\n", " ")
    print("content_preview:", preview)
    assert top.chunk_id == source.id
    assert top.company_document_id == DOCUMENT_ID
    assert top.similarity > 0.999
    print("smoke_retrieve_ok: True")
finally:
    db.close()
