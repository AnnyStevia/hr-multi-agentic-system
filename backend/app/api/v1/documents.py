from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from app.modules.documents.dependencies import get_document_service
from app.modules.documents.models import DocumentType
from app.modules.documents.schemas import DocumentResponse, PresignedDocumentUrlResponse
from app.modules.documents.service import DocumentService, build_document_response
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.hr_access import require_hr_staff
from app.modules.identity.models import User
from app.shared.exceptions import AppException

me_router = APIRouter(prefix="/me/documents", tags=["My Documents"])
employees_router = APIRouter(prefix="/employees", tags=["Employee Documents"])


def _parse_document_type(value: str) -> DocumentType:
    normalized = value.strip().lower()
    try:
        return DocumentType(normalized)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid document_type. Allowed: {[item.value for item in DocumentType]}",
        ) from exc


async def _read_upload(file: UploadFile) -> tuple[str | None, str | None, bytes]:
    content = await file.read()
    return file.filename, file.content_type, content


@me_router.get("", response_model=list[DocumentResponse])
def list_my_documents(
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> list[DocumentResponse]:
    try:
        return [build_document_response(doc) for doc in service.list_for_user(current_user.id)]
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@me_router.post("", response_model=DocumentResponse, status_code=201)
async def upload_my_document(
    document_type: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    parsed_type = _parse_document_type(document_type)
    filename, content_type, content = await _read_upload(file)
    try:
        document = service.upload_for_user(
            current_user.id,
            document_type=parsed_type,
            filename=filename,
            content_type=content_type,
            content=content,
        )
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return build_document_response(document)


@me_router.get("/{document_id}/url", response_model=PresignedDocumentUrlResponse)
def get_my_document_url(
    document_id: int,
    download: bool = Query(False),
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> PresignedDocumentUrlResponse:
    try:
        return service.presigned_url_for_user(current_user.id, document_id, download=download)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@employees_router.get(
    "/{employee_id}/documents",
    response_model=list[DocumentResponse],
)
def list_employee_documents(
    employee_id: int,
    _: User = Depends(require_hr_staff("documents:read")),
    service: DocumentService = Depends(get_document_service),
) -> list[DocumentResponse]:
    try:
        return [build_document_response(doc) for doc in service.list_for_employee(employee_id)]
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@employees_router.post(
    "/{employee_id}/documents",
    response_model=DocumentResponse,
    status_code=201,
)
async def upload_employee_document(
    employee_id: int,
    document_type: str = Form(...),
    file: UploadFile = File(...),
    _: User = Depends(require_hr_staff("documents:write")),
    service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    parsed_type = _parse_document_type(document_type)
    filename, content_type, content = await _read_upload(file)
    try:
        document = service.upload_for_employee(
            employee_id,
            document_type=parsed_type,
            filename=filename,
            content_type=content_type,
            content=content,
        )
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return build_document_response(document)


@employees_router.get(
    "/{employee_id}/documents/{document_id}/url",
    response_model=PresignedDocumentUrlResponse,
)
def get_employee_document_url(
    employee_id: int,
    document_id: int,
    download: bool = Query(False),
    _: User = Depends(require_hr_staff("documents:read")),
    service: DocumentService = Depends(get_document_service),
) -> PresignedDocumentUrlResponse:
    try:
        return service.presigned_url_for_employee(
            employee_id, document_id, download=download
        )
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@employees_router.delete(
    "/{employee_id}/documents/{document_id}",
    status_code=204,
)
def delete_employee_document(
    employee_id: int,
    document_id: int,
    _: User = Depends(require_hr_staff("documents:write")),
    service: DocumentService = Depends(get_document_service),
) -> None:
    try:
        service.delete_for_employee(employee_id, document_id)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
