from datetime import UTC, datetime
from io import BytesIO

from app.modules.documents.file_validation import ValidatedUpload, sanitize_filename, validate_employee_document
from app.modules.documents.models import Document, DocumentType
from app.modules.documents.repository import DocumentRepository
from app.modules.documents.schemas import DocumentResponse, PresignedDocumentUrlResponse
from app.modules.employees.repository import EmployeeRepository
from app.shared.exceptions import AppException
from app.shared.storage.base import StorageService
from app.shared.storage.exceptions import StorageException

PRESIGNED_URL_EXPIRES_IN = 300


class DocumentService:
    def __init__(
        self,
        repository: DocumentRepository,
        employees: EmployeeRepository,
        storage: StorageService,
    ):
        self.repository = repository
        self.employees = employees
        self.storage = storage

    def list_for_user(self, user_id: int) -> list[Document]:
        employee = self._require_employee_for_user(user_id)
        return self.repository.list_by_employee_id(employee.id)

    def list_for_employee(self, employee_id: int) -> list[Document]:
        self._require_employee(employee_id)
        return self.repository.list_by_employee_id(employee_id)

    def upload_for_user(
        self,
        user_id: int,
        *,
        document_type: DocumentType,
        filename: str | None,
        content_type: str | None,
        content: bytes,
    ) -> Document:
        employee = self._require_employee_for_user(user_id)
        return self._upload(employee.id, document_type, filename, content_type, content)

    def upload_for_employee(
        self,
        employee_id: int,
        *,
        document_type: DocumentType,
        filename: str | None,
        content_type: str | None,
        content: bytes,
    ) -> Document:
        self._require_employee(employee_id)
        return self._upload(employee_id, document_type, filename, content_type, content)

    def presigned_url_for_user(
        self, user_id: int, document_id: int, *, download: bool = False
    ) -> PresignedDocumentUrlResponse:
        employee = self._require_employee_for_user(user_id)
        document = self.repository.get_for_employee(document_id, employee.id)
        if document is None:
            raise AppException("Document not found", status_code=404)
        return self._presign(document, download=download)

    def presigned_url_for_employee(
        self, employee_id: int, document_id: int, *, download: bool = False
    ) -> PresignedDocumentUrlResponse:
        self._require_employee(employee_id)
        document = self.repository.get_for_employee(document_id, employee_id)
        if document is None:
            raise AppException("Document not found", status_code=404)
        return self._presign(document, download=download)

    def delete_for_employee(self, employee_id: int, document_id: int) -> None:
        self._require_employee(employee_id)
        document = self.repository.get_for_employee(document_id, employee_id)
        if document is None:
            raise AppException("Document not found", status_code=404)
        key = document.storage_key
        if key and key != "pending":
            try:
                self.storage.delete_file(key)
            except StorageException:
                pass
        self.repository.delete(document)

    def _upload(
        self,
        employee_id: int,
        document_type: DocumentType,
        filename: str | None,
        content_type: str | None,
        content: bytes,
    ) -> Document:
        upload = validate_employee_document(filename, content_type, content)
        now = datetime.now(UTC)
        document = Document(
            employee_id=employee_id,
            document_type=document_type,
            original_filename=upload.filename,
            content_type=upload.content_type,
            size_bytes=len(upload.content),
            storage_key="pending",
            uploaded_at=now,
        )
        self.repository.add(document, commit=False)
        storage_key = _build_storage_key(employee_id, document.id, upload)
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
        return self.repository.save(document)

    def _presign(self, document: Document, *, download: bool) -> PresignedDocumentUrlResponse:
        try:
            url = self.storage.generate_presigned_url(
                document.storage_key,
                expires_in=PRESIGNED_URL_EXPIRES_IN,
                filename=document.original_filename,
                download=download,
            )
        except StorageException as exc:
            raise AppException(exc.message, status_code=exc.status_code) from exc
        return PresignedDocumentUrlResponse(
            url=url,
            filename=document.original_filename,
            content_type=document.content_type,
            expires_in=PRESIGNED_URL_EXPIRES_IN,
            download=download,
        )

    def _require_employee_for_user(self, user_id: int):
        employee = self.employees.get_by_user_id(user_id)
        if employee is None:
            raise AppException("Employee profile not found", status_code=404)
        return employee

    def _require_employee(self, employee_id: int):
        employee = self.employees.get_by_id(employee_id)
        if employee is None:
            raise AppException("Employee not found", status_code=404)
        return employee


def build_document_response(document: Document) -> DocumentResponse:
    return DocumentResponse.model_validate(document)


def _build_storage_key(employee_id: int, document_id: int, upload: ValidatedUpload) -> str:
    safe = sanitize_filename(upload.filename)
    return f"employees/{employee_id}/documents/{document_id}/{safe}"
