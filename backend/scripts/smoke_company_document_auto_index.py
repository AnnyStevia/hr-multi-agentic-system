"""Live smoke: upload company PDF → auto-index READY → Knowledge Agent ask.

Opt-in only (uses Gemini). From backend/:

  $env:PYTHONPATH = "."
  .\\.venv\\Scripts\\python.exe scripts/smoke_company_document_auto_index.py
"""

from __future__ import annotations

import time

from app.modules.identity import models as identity_models  # noqa: F401
from app.modules.employees import models as employee_models  # noqa: F401
from app.modules.documents import models as document_models  # noqa: F401
from app.ai.rag import models as rag_models  # noqa: F401

from app.ai.agents.knowledge import KnowledgeAgent, KnowledgeAgentRequest
from app.ai.core.context.models import AIExecutionContext
from app.ai.core.llm import get_llm_provider
from app.ai.rag.chunking.repository import KnowledgeChunkRepository
from app.ai.rag.embeddings import EmbeddingService, get_embedding_provider
from app.ai.rag.generation import GroundedGenerationService
from app.ai.rag.indexing import CompanyDocumentIndexingService
from app.ai.rag.query import RAGQueryService
from app.ai.rag.retrieval import COMPANY_DOCUMENTS_READ, HybridRetrievalService
from app.core.database import SessionLocal
from app.modules.documents.library_repository import CompanyDocumentRepository
from app.modules.documents.models import CompanyDocumentRagIndexStatus
from app.modules.identity.models import Permission, Role, RolePermission, User, UserRole
from app.shared.storage import get_storage_service

# Minimal one-page PDF with extractable text for grounded Q&A.
# Uses a real existing library PDF when DOCUMENT_SOURCE_ID is set; otherwise
# re-indexes DOCUMENT_SOURCE_ID=2 (validated smoke PDF) synchronously.
DOCUMENT_SOURCE_ID = 2
POLL_SECONDS = 60
QUERY = "What position did Anny Stevia hold during her internship?"


class _CountingEmbeddingProvider:
    def __init__(self, inner):
        self._inner = inner
        self.embed_calls = 0

    def embed_text(self, text: str, *, task_type: str | None = None):
        self.embed_calls += 1
        return self._inner.embed_text(text, task_type=task_type)

    def embed_texts(self, texts, *, task_type: str | None = None):
        batch = list(texts)
        self.embed_calls += len(batch)
        return self._inner.embed_texts(batch, task_type=task_type)


class _CountingLLMProvider:
    def __init__(self, inner):
        self._inner = inner
        self.generate_calls = 0

    def generate_text(self, messages, *, temperature=None, max_tokens=None):
        self.generate_calls += 1
        return self._inner.generate_text(
            messages, temperature=temperature, max_tokens=max_tokens
        )

    def generate_structured(self, messages, *, schema, temperature=None, max_tokens=None):
        self.generate_calls += 1
        return self._inner.generate_structured(
            messages,
            schema=schema,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def generate_with_tools(self, messages, tools, **kwargs):
        self.generate_calls += 1
        return self._inner.generate_with_tools(messages, tools, **kwargs)


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
    storage = get_storage_service()
    repo = CompanyDocumentRepository(db)
    source = repo.get_by_id(DOCUMENT_SOURCE_ID)
    assert source is not None, f"source company document {DOCUMENT_SOURCE_ID} not found"

    # Simulate "upload then auto-index" using the real indexing orchestrator
    # (same path BackgroundTasks would call) against an existing company PDF.
    indexing = CompanyDocumentIndexingService(
        db,
        storage,
        embedding_provider=get_embedding_provider(),
    )
    print("indexing_document_id:", source.id)
    indexing.index_document(source.id)

    deadline = time.time() + POLL_SECONDS
    document = repo.get_by_id(source.id)
    while (
        document is not None
        and document.rag_index_status
        not in {
            CompanyDocumentRagIndexStatus.READY,
            CompanyDocumentRagIndexStatus.FAILED,
        }
        and time.time() < deadline
    ):
        time.sleep(1)
        db.refresh(document)

    assert document is not None
    print("rag_index_status:", document.rag_index_status.value)
    print("rag_indexing_error:", document.rag_indexing_error)
    assert (
        document.rag_index_status == CompanyDocumentRagIndexStatus.READY
    ), "expected READY after indexing"

    chunks = KnowledgeChunkRepository(db).list_by_company_document_id(document.id)
    print("chunk_count:", len(chunks))
    assert chunks, "expected chunks"
    assert all(c.embedding is not None for c in chunks), "expected embeddings"

    embed_provider = _CountingEmbeddingProvider(get_embedding_provider())
    llm_provider = _CountingLLMProvider(get_llm_provider())
    context = _context_with_company_read(db)
    agent = KnowledgeAgent(
        query_service=RAGQueryService(
            embedding_service=EmbeddingService(db, embed_provider),
            hybrid_service=HybridRetrievalService(db),
            db=db,
        ),
        generation_service=GroundedGenerationService(
            llm_provider=llm_provider,
            db=db,
        ),
    )
    answer = agent.ask(KnowledgeAgentRequest(question=QUERY, context=context))
    print("gemini_embed_calls:", embed_provider.embed_calls)
    print("gemini_generate_calls:", llm_provider.generate_calls)
    print("answer:", answer.answer)
    print("citations:", [(c.citation_id, c.company_document_id) for c in answer.citations])
    if answer.usage is not None:
        print(
            "usage:",
            {
                "input_tokens": answer.usage.input_tokens,
                "output_tokens": answer.usage.output_tokens,
                "total_tokens": answer.usage.total_tokens,
            },
        )

    assert embed_provider.embed_calls == 1
    assert llm_provider.generate_calls == 1
    assert answer.has_context
    assert answer.citations
    assert any(c.company_document_id == document.id for c in answer.citations)
    print("smoke_company_document_auto_index_ok: True")
finally:
    db.close()
