"""Document Agent factory (DI stays in the HTTP layer)."""

from __future__ import annotations

from app.ai.agents.documents.agent import DocumentsAgent
from app.ai.core.llm.base import LLMProvider
from app.ai.documents import DocumentUnderstandingService
from app.ai.documents.access import AuthorizedDocumentAccess
from app.modules.documents.library_service import (
    CompanyDocumentService,
    PrivateDocumentService,
)
from app.modules.documents.service import DocumentService


def build_documents_agent(
    *,
    llm_provider: LLMProvider,
    company_documents: CompanyDocumentService,
    employee_documents: DocumentService,
    private_documents: PrivateDocumentService,
    understanding: DocumentUnderstandingService | None = None,
) -> DocumentsAgent:
    """Construct read-only DocumentsAgent with tools + understanding wired."""
    if understanding is None:
        access = AuthorizedDocumentAccess(
            company_documents=company_documents,
            employee_documents=employee_documents,
            private_documents=private_documents,
        )
        understanding = DocumentUnderstandingService(
            access,
            llm_provider=llm_provider,
        )
    return DocumentsAgent(
        llm_provider=llm_provider,
        company_documents=company_documents,
        employee_documents=employee_documents,
        private_documents=private_documents,
        understanding=understanding,
    )
