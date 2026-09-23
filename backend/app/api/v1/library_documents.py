from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from app.modules.documents.dependencies import (
    get_company_document_service,
    get_private_document_service,
)
from app.modules.documents.library_service import (
    CompanyDocumentService,
    PrivateDocumentService,
    build_company_document_response,
    build_private_document_response,
)
from app.modules.documents.models import CompanyDocumentStatus
from app.modules.documents.schemas import (
    CompanyDocumentCategoryResponse,
    CompanyDocumentResponse,
    CompanyDocumentUpdateRequest,
    PresignedDocumentUrlResponse,
    PrivateDocumentResponse,
    PrivateDocumentUpdateRequest,
)
from app.modules.identity.dependencies import get_current_user, require_permissions
from app.modules.identity.hr_access import require_hr_staff
from app.modules.identity.models import User
from app.shared.exceptions import AppException

company_router = APIRouter(prefix="/company-documents", tags=["Company Documents"])
private_router = APIRouter(prefix="/me/private-documents", tags=["Private Documents"])


async def _read_upload(file: UploadFile) -> tuple[str | None, str | None, bytes]:
    content = await file.read()
    return file.filename, file.content_type, content


def _parse_status(value: str | None) -> CompanyDocumentStatus | None:
    if value is None or not value.strip():
        return None
    try:
        return CompanyDocumentStatus(value.strip().lower())
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status. Allowed: {[item.value for item in CompanyDocumentStatus]}",
        ) from exc


@company_router.get("/categories", response_model=list[CompanyDocumentCategoryResponse])
def list_company_document_categories(
    _: User = Depends(require_permissions("company_documents:read")),
    service: CompanyDocumentService = Depends(get_company_document_service),
) -> list[CompanyDocumentCategoryResponse]:
    return [
        CompanyDocumentCategoryResponse.model_validate(item)
        for item in service.list_categories()
    ]


@company_router.get("", response_model=list[CompanyDocumentResponse])
def list_company_documents(
    q: str | None = Query(None),
    category_id: int | None = Query(None),
    status: str | None = Query(None),
    current_user: User = Depends(require_permissions("company_documents:read")),
    service: CompanyDocumentService = Depends(get_company_document_service),
) -> list[CompanyDocumentResponse]:
    try:
        docs = service.list_documents(
            user=current_user,
            q=q,
            category_id=category_id,
            status=_parse_status(status),
        )
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return [build_company_document_response(doc) for doc in docs]


@company_router.post("", response_model=CompanyDocumentResponse, status_code=201)
async def upload_company_document(
    title: str = Form(...),
    category_id: int = Form(...),
    description: str | None = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(require_hr_staff("company_documents:write")),
    service: CompanyDocumentService = Depends(get_company_document_service),
) -> CompanyDocumentResponse:
    filename, content_type, content = await _read_upload(file)
    try:
        document = service.upload(
            user=current_user,
            title=title,
            description=description,
            category_id=category_id,
            filename=filename,
            content_type=content_type,
            content=content,
        )
        # Reload relationships for response
        document = service._require_document(document.id)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return build_company_document_response(document)


@company_router.patch("/{document_id}", response_model=CompanyDocumentResponse)
def update_company_document(
    document_id: int,
    payload: CompanyDocumentUpdateRequest,
    _: User = Depends(require_hr_staff("company_documents:write")),
    service: CompanyDocumentService = Depends(get_company_document_service),
) -> CompanyDocumentResponse:
    try:
        document = service.update(document_id, payload)
        document = service._require_document(document.id)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return build_company_document_response(document)


@company_router.delete("/{document_id}", status_code=204)
def delete_company_document(
    document_id: int,
    _: User = Depends(require_hr_staff("company_documents:write")),
    service: CompanyDocumentService = Depends(get_company_document_service),
) -> None:
    try:
        service.delete(document_id)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@company_router.get("/{document_id}/url", response_model=PresignedDocumentUrlResponse)
def get_company_document_url(
    document_id: int,
    download: bool = Query(False),
    current_user: User = Depends(require_permissions("company_documents:read")),
    service: CompanyDocumentService = Depends(get_company_document_service),
) -> PresignedDocumentUrlResponse:
    try:
        return service.presigned_url(document_id, user=current_user, download=download)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@private_router.get("", response_model=list[PrivateDocumentResponse])
def list_my_private_documents(
    current_user: User = Depends(get_current_user),
    service: PrivateDocumentService = Depends(get_private_document_service),
) -> list[PrivateDocumentResponse]:
    try:
        return [
            build_private_document_response(doc)
            for doc in service.list_for_user(current_user.id)
        ]
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@private_router.post("", response_model=PrivateDocumentResponse, status_code=201)
async def upload_my_private_document(
    title: str = Form(...),
    description: str | None = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    service: PrivateDocumentService = Depends(get_private_document_service),
) -> PrivateDocumentResponse:
    filename, content_type, content = await _read_upload(file)
    try:
        document = service.upload(
            current_user.id,
            title=title,
            description=description,
            filename=filename,
            content_type=content_type,
            content=content,
        )
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return build_private_document_response(document)


@private_router.patch("/{document_id}", response_model=PrivateDocumentResponse)
def update_my_private_document(
    document_id: int,
    payload: PrivateDocumentUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: PrivateDocumentService = Depends(get_private_document_service),
) -> PrivateDocumentResponse:
    try:
        document = service.update(current_user.id, document_id, payload)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return build_private_document_response(document)


@private_router.delete("/{document_id}", status_code=204)
def delete_my_private_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    service: PrivateDocumentService = Depends(get_private_document_service),
) -> None:
    try:
        service.delete(current_user.id, document_id)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@private_router.get("/{document_id}/url", response_model=PresignedDocumentUrlResponse)
def get_my_private_document_url(
    document_id: int,
    download: bool = Query(False),
    current_user: User = Depends(get_current_user),
    service: PrivateDocumentService = Depends(get_private_document_service),
) -> PresignedDocumentUrlResponse:
    try:
        return service.presigned_url(current_user.id, document_id, download=download)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
