from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.ai.agents.recruitment import (
    CvExtractionResponse,
    CvExtractionService,
    RecruitmentExtractionError,
    RecruitmentExtractionUnsupportedError,
    RecruitmentExtractionValidationError,
)
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


def get_cv_extraction_service() -> CvExtractionService:
    return CvExtractionService()


@router.post("/cv/extract", response_model=CvExtractionResponse)
async def extract_cv_fields(
    cv: UploadFile = File(...),
    _candidate: User = Depends(require_careers_access),
    service: CvExtractionService = Depends(get_cv_extraction_service),
) -> CvExtractionResponse:
    """Extract structured fields from an uploaded CV PDF for form pre-fill.

    Does not persist results or mutate candidate/user records.
    """
    content = await cv.read()
    try:
        extraction = service.extract_from_upload(
            filename=cv.filename,
            content_type=cv.content_type,
            content=content,
        )
        return CvExtractionResponse(extraction=extraction)
    except RecruitmentExtractionValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc
    except RecruitmentExtractionUnsupportedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc
    except RecruitmentExtractionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=exc.message,
        ) from exc


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
