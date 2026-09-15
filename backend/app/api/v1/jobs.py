from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.identity.dependencies import require_permissions
from app.modules.identity.models import User
from app.modules.recruitment.application_service import (
    ApplicationService,
    build_application_list_item,
)
from app.modules.recruitment.dependencies import get_application_service, get_job_service
from app.modules.recruitment.schemas import ApplicationListItem, JobCreateRequest, JobResponse, JobUpdateRequest
from app.modules.recruitment.service import JobService, build_job_response
from app.shared.exceptions import AppException

router = APIRouter(prefix="/jobs", tags=["Jobs"])


def _handle(exc: AppException) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("", response_model=list[JobResponse])
def list_jobs(
    _user: User = Depends(require_permissions("recruitment:read")),
    job_service: JobService = Depends(get_job_service),
) -> list[JobResponse]:
    return [build_job_response(job) for job in job_service.list_jobs()]


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreateRequest,
    current_user: User = Depends(require_permissions("recruitment:write")),
    job_service: JobService = Depends(get_job_service),
) -> JobResponse:
    try:
        return build_job_response(job_service.create_job(payload, created_by_user_id=current_user.id))
    except AppException as exc:
        _handle(exc)


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: int,
    _user: User = Depends(require_permissions("recruitment:read")),
    job_service: JobService = Depends(get_job_service),
) -> JobResponse:
    try:
        return build_job_response(job_service.get_job(job_id))
    except AppException as exc:
        _handle(exc)


@router.patch("/{job_id}", response_model=JobResponse)
def update_job(
    job_id: int,
    payload: JobUpdateRequest,
    _user: User = Depends(require_permissions("recruitment:write")),
    job_service: JobService = Depends(get_job_service),
) -> JobResponse:
    try:
        return build_job_response(job_service.update_job(job_id, payload))
    except AppException as exc:
        _handle(exc)


@router.get("/{job_id}/applications", response_model=list[ApplicationListItem])
def list_job_applications(
    job_id: int,
    _user: User = Depends(require_permissions("recruitment:read")),
    application_service: ApplicationService = Depends(get_application_service),
) -> list[ApplicationListItem]:
    try:
        return [
            build_application_list_item(application)
            for application in application_service.list_for_job(job_id)
        ]
    except AppException as exc:
        _handle(exc)


@router.post("/{job_id}/publish", response_model=JobResponse)
def publish_job(
    job_id: int,
    _user: User = Depends(require_permissions("recruitment:write")),
    job_service: JobService = Depends(get_job_service),
) -> JobResponse:
    try:
        return build_job_response(job_service.publish_job(job_id))
    except AppException as exc:
        _handle(exc)


@router.post("/{job_id}/close", response_model=JobResponse)
def close_job(
    job_id: int,
    _user: User = Depends(require_permissions("recruitment:write")),
    job_service: JobService = Depends(get_job_service),
) -> JobResponse:
    try:
        return build_job_response(job_service.close_job(job_id))
    except AppException as exc:
        _handle(exc)
