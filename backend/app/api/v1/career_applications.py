from fastapi import APIRouter, Depends, HTTPException

from app.modules.identity.models import User
from app.modules.onboarding.dependencies import require_careers_access
from app.modules.recruitment.application_service import (
    ApplicationService,
    build_application_detail,
)
from app.modules.recruitment.dependencies import get_application_service
from app.modules.recruitment.schemas import ApplicationDetail, CandidateApplicationSummary
from app.shared.exceptions import AppException

router = APIRouter(prefix="/careers", tags=["Careers"])


@router.get("/my-applications", response_model=list[CandidateApplicationSummary])
def list_my_applications(
    current_user: User = Depends(require_careers_access),
    application_service: ApplicationService = Depends(get_application_service),
) -> list[CandidateApplicationSummary]:
    try:
        applications = application_service.list_own(current_user)
        return [
            CandidateApplicationSummary(
                id=application.id,
                job_id=application.job_id,
                status=application.status,
                submitted_at=application.submitted_at,
                job_title=application.job.title,
            )
            for application in applications
        ]
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


applications_router = APIRouter(prefix="/careers/applications", tags=["Careers"])


@applications_router.get("/{application_id}", response_model=ApplicationDetail)
def get_own_application(
    application_id: int,
    current_user: User = Depends(require_careers_access),
    application_service: ApplicationService = Depends(get_application_service),
) -> ApplicationDetail:
    try:
        application = application_service.get_own(current_user, application_id)
        return build_application_detail(application)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
