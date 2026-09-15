from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.identity.dependencies import require_permissions
from app.modules.identity.models import User
from app.modules.interviews.dependencies import get_interview_service
from app.modules.interviews.schemas import InterviewCreateRequest, InterviewDetailResponse, InterviewSummary
from app.modules.interviews.service import InterviewService, build_interview_detail, build_interview_summary
from app.shared.exceptions import AppException

router = APIRouter(prefix="/interviews", tags=["Interviews"])


def _handle(exc: AppException) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/applications/{application_id}", response_model=list[InterviewSummary])
def list_application_interviews(
    application_id: int,
    _user: User = Depends(require_permissions("recruitment:read")),
    interview_service: InterviewService = Depends(get_interview_service),
) -> list[InterviewSummary]:
    try:
        return [
            build_interview_summary(interview)
            for interview in interview_service.list_for_application(application_id)
        ]
    except AppException as exc:
        _handle(exc)


@router.post(
    "/applications/{application_id}",
    response_model=InterviewDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_interview_invitation(
    application_id: int,
    payload: InterviewCreateRequest,
    current_user: User = Depends(require_permissions("recruitment:write")),
    interview_service: InterviewService = Depends(get_interview_service),
) -> InterviewDetailResponse:
    try:
        interview = interview_service.create_invitation(
            application_id,
            payload,
            created_by=current_user,
        )
        return build_interview_detail(interview)
    except AppException as exc:
        _handle(exc)


@router.get("/{interview_id}", response_model=InterviewDetailResponse)
def get_interview(
    interview_id: int,
    _user: User = Depends(require_permissions("recruitment:read")),
    interview_service: InterviewService = Depends(get_interview_service),
) -> InterviewDetailResponse:
    try:
        return build_interview_detail(interview_service.get_for_hr(interview_id))
    except AppException as exc:
        _handle(exc)
