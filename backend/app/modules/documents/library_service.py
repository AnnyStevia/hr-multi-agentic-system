from __future__ import annotations

from io import BytesIO

from app.modules.documents.file_validation import (
    ValidatedUpload,
    sanitize_filename,
    validate_employee_document,
)
from app.modules.documents.library_repository import (
    CompanyDocumentRepository,
    PrivateDocumentRepository,
)
from app.modules.documents.models import (
    CompanyDocument,
    CompanyDocumentRagIndexStatus,
    CompanyDocumentStatus,
    PrivateDocument,
)
from app.modules.documents.schemas import (
    CompanyDocumentResponse,
    CompanyDocumentUpdateRequest,
    PresignedDocumentUrlResponse,
    PrivateDocumentResponse,
    PrivateDocumentUpdateRequest,
)
from app.modules.employees.repository import EmployeeRepository
from app.modules.identity.hr_access import HR_STAFF_ROLE_NAMES
from app.modules.identity.models import User
from app.shared.exceptions import AppException
from app.shared.storage.base import StorageService
from app.shared.storage.exceptions import StorageException

PRESIGNED_URL_EXPIRES_IN = 300


class CompanyDocumentService:
    def __init__(
        self,
        repository: CompanyDocumentRepository,
        storage: StorageService,
    ):
        self.repository = repository
        self.storage = storage

    def list_categories(self):
        return self.repository.list_categories(active_only=True)

    def list_documents(
        self,
        *,
        user: User,
        q: str | None = None,
        category_id: int | None = None,
        status: CompanyDocumentStatus | None = None,
    ) -> list[CompanyDocument]:
        effective_status = status
        if not _is_hr_staff(user):
            # Employees only see active library documents.
            effective_status = CompanyDocumentStatus.ACTIVE
        return self.repository.list_documents(
            q=q, category_id=category_id, status=effective_status
        )

    def upload(
        self,
        *,
        user: User,
        title: str,
        description: str | None,
        category_id: int,
        filename: str | None,
        content_type: str | None,
        content: bytes,
    ) -> CompanyDocument:
        category = self.repository.get_category(category_id)
        if category is None or not category.is_active:
            raise AppException("Category not found", status_code=400)
        cleaned_title = title.strip()
        if not cleaned_title:
            raise AppException("Title is required", status_code=400)

        upload = validate_employee_document(filename, content_type, content)
        document = CompanyDocument(
            title=cleaned_title,
            description=_optional_text(description),
            category_id=category.id,
            original_filename=upload.filename,
            content_type=upload.content_type,
            size_bytes=len(upload.content),
            storage_key="pending",
            version=1,
            uploaded_by_user_id=user.id,
            status=CompanyDocumentStatus.ACTIVE,
            rag_index_status=CompanyDocumentRagIndexStatus.PENDING,
        )
        self.repository.add(document, commit=False)
        storage_key = _company_storage_key(document.id, upload)
        try:
            self.storage.upload_file(
                storage_key,
                BytesIO(upload.content),
                content_type=upload.content_type,
            )
        except StorageException as exc:
            self.repository.db.rollback()
            raise AppException(exc.message, status_code=exc.status_code) from exc
        document.storage_key = storage_key
        try:
            return self.repository.save(document)
        except Exception:
            try:
                self.storage.delete_file(storage_key)
            except StorageException:
                pass
            self.repository.db.rollback()
            raise

    def update(
        self, document_id: int, payload: CompanyDocumentUpdateRequest
    ) -> CompanyDocument:
        document = self._require_document(document_id)
        data = payload.model_dump(exclude_unset=True)
        if "title" in data and data["title"] is not None:
            title = data["title"].strip()
            if not title:
                raise AppException("Title is required", status_code=400)
            document.title = title
        if "description" in data:
            document.description = _optional_text(data["description"])
        if "category_id" in data and data["category_id"] is not None:
            category = self.repository.get_category(data["category_id"])
            if category is None or not category.is_active:
                raise AppException("Category not found", status_code=400)
            document.category_id = category.id
        if "status" in data and data["status"] is not None:
            document.status = data["status"]
        return self.repository.save(document)

    def delete(self, document_id: int) -> None:
        document = self._require_document(document_id)
        key = document.storage_key
        if key and key != "pending":
            try:
                self.storage.delete_file(key)
            except StorageException:
                pass
        self.repository.delete(document)

    def presigned_url(
        self, document_id: int, *, user: User, download: bool = False
    ) -> PresignedDocumentUrlResponse:
        document = self._require_document(document_id)
        if (
            not _is_hr_staff(user)
            and document.status != CompanyDocumentStatus.ACTIVE
        ):
            raise AppException("Document not found", status_code=404)
        return _presign(
            self.storage,
            storage_key=document.storage_key,
            filename=document.original_filename,
            content_type=document.content_type,
            download=download,
        )

    def _require_document(self, document_id: int) -> CompanyDocument:
        document = self.repository.get_by_id(document_id)
        if document is None:
            raise AppException("Document not found", status_code=404)
        return document


class PrivateDocumentService:
    def __init__(
        self,
        repository: PrivateDocumentRepository,
        employees: EmployeeRepository,
        storage: StorageService,
    ):
        self.repository = repository
        self.employees = employees
        self.storage = storage

    def list_for_user(self, user_id: int) -> list[PrivateDocument]:
        employee = self._require_employee_for_user(user_id)
        return self.repository.list_for_owner(employee.id)

    def upload(
        self,
        user_id: int,
        *,
        title: str,
        description: str | None,
        filename: str | None,
        content_type: str | None,
        content: bytes,
    ) -> PrivateDocument:
        employee = self._require_employee_for_user(user_id)
        cleaned_title = title.strip()
        if not cleaned_title:
            raise AppException("Title is required", status_code=400)
        upload = validate_employee_document(filename, content_type, content)
        document = PrivateDocument(
            owner_employee_id=employee.id,
            title=cleaned_title,
            description=_optional_text(description),
            original_filename=upload.filename,
            content_type=upload.content_type,
            size_bytes=len(upload.content),
            storage_key="pending",
            uploaded_by_user_id=user_id,
        )
        self.repository.add(document, commit=False)
        storage_key = _private_storage_key(employee.id, document.id, upload)
        try:
            self.storage.upload_file(
                storage_key,
                BytesIO(upload.content),
                content_type=upload.content_type,
            )
        except StorageException as exc:
            self.repository.db.rollback()
            raise AppException(exc.message, status_code=exc.status_code) from exc
        document.storage_key = storage_key
        try:
            return self.repository.save(document)
        except Exception:
            try:
                self.storage.delete_file(storage_key)
            except StorageException:
                pass
            self.repository.db.rollback()
            raise

    def update(
        self, user_id: int, document_id: int, payload: PrivateDocumentUpdateRequest
    ) -> PrivateDocument:
        document = self._require_owned(user_id, document_id)
        data = payload.model_dump(exclude_unset=True)
        if "title" in data and data["title"] is not None:
            title = data["title"].strip()
            if not title:
                raise AppException("Title is required", status_code=400)
            document.title = title
        if "description" in data:
            document.description = _optional_text(data["description"])
        return self.repository.save(document)

    def delete(self, user_id: int, document_id: int) -> None:
        document = self._require_owned(user_id, document_id)
        key = document.storage_key
        if key and key != "pending":
            try:
                self.storage.delete_file(key)
            except StorageException:
                pass
        self.repository.delete(document)

    def presigned_url(
        self, user_id: int, document_id: int, *, download: bool = False
    ) -> PresignedDocumentUrlResponse:
        document = self._require_owned(user_id, document_id)
        return _presign(
            self.storage,
            storage_key=document.storage_key,
            filename=document.original_filename,
            content_type=document.content_type,
            download=download,
        )

    def _require_employee_for_user(self, user_id: int):
        employee = self.employees.get_by_user_id(user_id)
        if employee is None:
            raise AppException("Employee profile not found", status_code=404)
        return employee

    def _require_owned(self, user_id: int, document_id: int) -> PrivateDocument:
        employee = self._require_employee_for_user(user_id)
        document = self.repository.get_for_owner(document_id, employee.id)
        if document is None:
            raise AppException("Document not found", status_code=404)
        return document


def build_company_document_response(document: CompanyDocument) -> CompanyDocumentResponse:
    uploader = document.uploaded_by
    uploaded_by_name = (
        f"{uploader.first_name} {uploader.last_name}".strip()
        if uploader is not None
        else ""
    )
    category = document.category
    return CompanyDocumentResponse(
        id=document.id,
        title=document.title,
        description=document.description,
        category_id=document.category_id,
        category_slug=category.slug if category is not None else "",
        category_label=category.label if category is not None else "",
        original_filename=document.original_filename,
        content_type=document.content_type,
        size_bytes=document.size_bytes,
        version=document.version,
        uploaded_by_user_id=document.uploaded_by_user_id,
        uploaded_by_name=uploaded_by_name,
        status=document.status,
        rag_index_status=document.rag_index_status,
        rag_indexed_at=document.rag_indexed_at,
        rag_indexing_error=document.rag_indexing_error,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def build_private_document_response(document: PrivateDocument) -> PrivateDocumentResponse:
    return PrivateDocumentResponse.model_validate(document)


def _is_hr_staff(user: User) -> bool:
    roles = {ur.role.name for ur in user.user_roles}
    return bool(HR_STAFF_ROLE_NAMES & roles)


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _presign(
    storage: StorageService,
    *,
    storage_key: str,
    filename: str,
    content_type: str,
    download: bool,
) -> PresignedDocumentUrlResponse:
    try:
        url = storage.generate_presigned_url(
            storage_key,
            expires_in=PRESIGNED_URL_EXPIRES_IN,
            filename=filename,
            download=download,
        )
    except StorageException as exc:
        raise AppException(exc.message, status_code=exc.status_code) from exc
    return PresignedDocumentUrlResponse(
        url=url,
        filename=filename,
        content_type=content_type,
        expires_in=PRESIGNED_URL_EXPIRES_IN,
        download=download,
    )


def _company_storage_key(document_id: int, upload: ValidatedUpload) -> str:
    safe = sanitize_filename(upload.filename)
    return f"company-documents/{document_id}/{safe}"


def _private_storage_key(
    employee_id: int, document_id: int, upload: ValidatedUpload
) -> str:
    safe = sanitize_filename(upload.filename)
    return f"employees/{employee_id}/private/{document_id}/{safe}"
