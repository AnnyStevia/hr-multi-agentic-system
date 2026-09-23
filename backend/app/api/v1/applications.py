from fastapi import APIRouter, Depends, HTTPException

from app.modules.identity.hr_access import require_hr_staff
from app.modules.identity.models import User
from app.modules.recruitment.application_service import (
    ApplicationService,
    build_application_detail,
    build_application_list_item,
)
from app.modules.recruitment.dependencies import get_application_service
from app.modules.recruitment.schemas import ApplicationDetail, ApplicationListItem, ApplicationStatusUpdateRequest, PresignedDocumentResponse
from app.shared.exceptions import AppException

router = APIRouter(prefix="/applications", tags=["Applications"])


def _handle(exc: AppException) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/{application_id}", response_model=ApplicationDetail)
def get_application(
    application_id: int,
    _user: User = Depends(require_hr_staff("recruitment:read")),
    application_service: ApplicationService = Depends(get_application_service),
) -> ApplicationDetail:
    try:
        return build_application_detail(application_service.get_for_hr(application_id))
    except AppException as exc:
        _handle(exc)


@router.patch("/{application_id}/status", response_model=ApplicationDetail)
def update_application_status(
    application_id: int,
    payload: ApplicationStatusUpdateRequest,
    _user: User = Depends(require_hr_staff("recruitment:write")),
    application_service: ApplicationService = Depends(get_application_service),
) -> ApplicationDetail:
    try:
        return build_application_detail(
            application_service.update_status(application_id, payload.status)
        )
    except AppException as exc:
        _handle(exc)


@router.get("/{application_id}/documents/{document_id}/url", response_model=PresignedDocumentResponse)
def get_application_document_url(
    application_id: int,
    document_id: int,
    download: bool = False,
    _user: User = Depends(require_hr_staff("recruitment:read")),
    application_service: ApplicationService = Depends(get_application_service),
) -> PresignedDocumentResponse:
    try:
        return application_service.presigned_document_url(
            application_id,
            document_id,
            download=download,
        )
    except AppException as exc:
        _handle(exc)
