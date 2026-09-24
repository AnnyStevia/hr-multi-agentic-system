"""Access filters mirroring Company Document Library HTTP rules."""

from __future__ import annotations

from sqlalchemy.sql.elements import ColumnElement

from app.ai.core.context.models import AIExecutionContext
from app.ai.rag.retrieval.exceptions import RetrievalAuthorizationError
from app.modules.documents.models import CompanyDocument, CompanyDocumentStatus
from app.modules.identity.hr_access import HR_STAFF_ROLE_NAMES

COMPANY_DOCUMENTS_READ = "company_documents:read"


def is_hr_staff(context: AIExecutionContext) -> bool:
    """True when context has admin or hr role (same set as Core HR library)."""
    return bool(context.role_names.intersection(HR_STAFF_ROLE_NAMES))


def require_company_documents_read(context: AIExecutionContext) -> None:
    if COMPANY_DOCUMENTS_READ not in context.permission_names:
        raise RetrievalAuthorizationError(
            f"Missing permission: {COMPANY_DOCUMENTS_READ}"
        )


def company_document_eligibility_clause(
    context: AIExecutionContext,
) -> ColumnElement[bool] | None:
    """SQL filter for company_documents eligibility.

    Non-HR (employee/manager): ACTIVE only — mirrors list_documents / download.
    HR/admin: no status restriction — mirrors HR list with status=None.
    Returns None when no extra status clause is needed.
    """
    if is_hr_staff(context):
        return None
    return CompanyDocument.status == CompanyDocumentStatus.ACTIVE
