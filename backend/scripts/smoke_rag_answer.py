"""Smoke: grounded RAG answer (1 embed + 1 generate; no retries).

Run from backend/ after doc 2 is chunked+embedded:

  $env:PYTHONPATH = "."
  .\\.venv\\Scripts\\python.exe scripts/smoke_rag_answer.py
"""

from app.modules.identity import models as identity_models  # noqa: F401
from app.modules.employees import models as employee_models  # noqa: F401
from app.modules.documents import models as document_models  # noqa: F401
from app.ai.rag import models as rag_models  # noqa: F401

from app.ai.core.context.models import AIExecutionContext
from app.ai.core.llm import get_llm_provider
from app.ai.rag.config import rag_settings
from app.ai.rag.embeddings import EmbeddingService, get_embedding_provider
from app.ai.rag.generation import GroundedGenerationService, RAGGenerationRequest
from app.ai.rag.query import RAGQueryRequest, RAGQueryService
from app.ai.rag.retrieval import COMPANY_DOCUMENTS_READ, HybridRetrievalService
from app.core.database import SessionLocal
from app.modules.identity.models import Permission, Role, RolePermission, User, UserRole

QUERY = "What position did Anny Stevia hold during her internship?"


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


class _CountingEmbeddingProvider:
    def __init__(self, inner):
        self._inner = inner
        self.embed_calls = 0

    def embed_text(self, text: str, *, task_type: str | None = None):
        self.embed_calls += 1
        return self._inner.embed_text(text, task_type=task_type)

    def embed_texts(self, texts, *, task_type: str | None = None):
        self.embed_calls += len(list(texts))
        return self._inner.embed_texts(texts, task_type=task_type)


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


db = SessionLocal()
try:
    context = _context_with_company_read(db)
    embed_provider = _CountingEmbeddingProvider(get_embedding_provider())
    llm_provider = _CountingLLMProvider(get_llm_provider())

    query_service = RAGQueryService(
        embedding_service=EmbeddingService(db, embed_provider),
        hybrid_service=HybridRetrievalService(db),
        db=db,
    )
    generation_service = GroundedGenerationService(
        llm_provider=llm_provider,
        db=db,
    )

    print("query:", QUERY)
    query_result = query_service.query(RAGQueryRequest(query=QUERY, context=context))
    answer = generation_service.generate(
        RAGGenerationRequest(query_result=query_result, context=context)
    )

    print("gemini_embed_calls:", embed_provider.embed_calls)
    print("gemini_generate_calls:", llm_provider.generate_calls)
    assert embed_provider.embed_calls == 1, "expected exactly one embedding call"
    assert llm_provider.generate_calls == 1, "expected exactly one generation call"

    print("embedding_model:", answer.embedding_model)
    print("retrieval_count:", answer.retrieval_count)
    print("selected_context_count:", answer.selected_context_count)
    print("generation_model:", answer.model)
    print("has_context:", answer.has_context)
    print("answer:", answer.answer)
    print(
        "citation_ids:",
        [c.citation_id for c in answer.citations],
    )
    print(
        "document_ids:",
        [c.company_document_id for c in answer.citations],
    )
    print(
        "page_ranges:",
        [f"{c.page_start}-{c.page_end}" for c in answer.citations],
    )
    if answer.usage is not None:
        print(
            "usage:",
            {
                "input_tokens": answer.usage.input_tokens,
                "output_tokens": answer.usage.output_tokens,
                "thinking_tokens": answer.usage.thinking_tokens,
                "total_tokens": answer.usage.total_tokens,
            },
        )
    else:
        print("usage:", None)

    assert answer.has_context, "expected retrieved context for doc 2"
    assert answer.answer.strip(), "expected non-empty answer"
    assert answer.citations, "expected at least one citation"
    assert all(c.company_document_id == 2 for c in answer.citations)
    assert answer.embedding_model == rag_settings.rag_embedding_model
    print("smoke_rag_answer_ok: True")
finally:
    db.close()
