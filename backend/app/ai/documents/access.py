"""Authorized document access for Document Understanding."""

from __future__ import annotations

from app.ai.core.context.models import AIExecutionContext
from app.ai.documents.exceptions import (
    DocumentUnderstandingAuthorizationError,
    DocumentUnderstandingError,
    DocumentUnderstandingNotFoundError,
    DocumentUnderstandingUnsupportedError,
)
from app.ai.documents.schemas import DocumentRef, DocumentSourceType
from app.modules.documents.content_payload import AuthorizedDocumentBytes
from app.modules.documents.library_service import (
    CompanyDocumentService,
    PrivateDocumentService,
)
from app.modules.documents.service import DocumentService
from app.modules.identity.hr_access import HR_STAFF_ROLE_NAMES
from app.shared.exceptions import AppException

COMPANY_DOCUMENTS_READ = "company_documents:read"
DOCUMENTS_READ = "documents:read"


class AuthorizedDocumentAccess:
    """Resolve one authorized document to bytes via domain services only."""

    def __init__(
        self,
        *,
        company_documents: CompanyDocumentService,
        employee_documents: DocumentService,
        private_documents: PrivateDocumentService,
    ) -> None:
        self._company = company_documents
        self._employees = employee_documents
        self._private = private_documents

    def resolve(
        self, ref: DocumentRef, context: AIExecutionContext
    ) -> tuple[AuthorizedDocumentBytes, DocumentSourceType]:
        if ref.source_type == DocumentSourceType.APPLICATION:
            raise DocumentUnderstandingUnsupportedError(
                "Candidate application documents are not supported by Document Understanding"
            )
        if ref.source_type == DocumentSourceType.COMPANY:
            return self._resolve_company(ref, context), DocumentSourceType.COMPANY
        if ref.source_type == DocumentSourceType.PRIVATE:
            return self._resolve_private(ref, context), DocumentSourceType.PRIVATE
        if ref.source_type == DocumentSourceType.EMPLOYEE:
            return self._resolve_employee(ref, context), DocumentSourceType.EMPLOYEE
        raise DocumentUnderstandingUnsupportedError(
            f"Unsupported document source type: {ref.source_type}"
        )

    def _resolve_company(
        self, ref: DocumentRef, context: AIExecutionContext
    ) -> AuthorizedDocumentBytes:
        if COMPANY_DOCUMENTS_READ not in context.permission_names:
            raise DocumentUnderstandingAuthorizationError(
                f"Missing permission: {COMPANY_DOCUMENTS_READ}"
            )
        try:
            return self._company.load_active_file_bytes(ref.document_id)
        except AppException as exc:
            raise _map_app_exception(exc) from exc

    def _resolve_private(
        self, ref: DocumentRef, context: AIExecutionContext
    ) -> AuthorizedDocumentBytes:
        try:
            return self._private.load_file_bytes_for_owner(
                context.user_id, ref.document_id
            )
        except AppException as exc:
            raise _map_app_exception(exc) from exc

    def _resolve_employee(
        self, ref: DocumentRef, context: AIExecutionContext
    ) -> AuthorizedDocumentBytes:
        # Self access
        if context.employee_id is not None and (
            ref.employee_id is None or ref.employee_id == context.employee_id
        ):
            try:
                return self._employees.load_file_bytes_for_user(
                    context.user_id, ref.document_id
                )
            except AppException as exc:
                # Fall through to HR path only when employee_id explicitly targets another person
                if ref.employee_id is None or ref.employee_id == context.employee_id:
                    raise _map_app_exception(exc) from exc

        # HR/Admin path for another employee
        target_employee_id = ref.employee_id
        if target_employee_id is None:
            raise DocumentUnderstandingNotFoundError("Document not found")

        is_hr_staff = bool(context.role_names.intersection(HR_STAFF_ROLE_NAMES))
        if not is_hr_staff or DOCUMENTS_READ not in context.permission_names:
            raise DocumentUnderstandingAuthorizationError(
                "Not authorized to access employee documents"
            )
        try:
            return self._employees.load_file_bytes_for_employee(
                target_employee_id, ref.document_id
            )
        except AppException as exc:
            raise _map_app_exception(exc) from exc


def _map_app_exception(exc: AppException) -> DocumentUnderstandingError:
    if exc.status_code == 404:
        return DocumentUnderstandingNotFoundError(exc.message or "Document not found")
    if exc.status_code in {401, 403}:
        return DocumentUnderstandingAuthorizationError(
            exc.message or "Not authorized"
        )
    return DocumentUnderstandingError(exc.message or "Document access failed")
