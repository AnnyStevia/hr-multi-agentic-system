from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.identity.dependencies import require_roles
from app.modules.identity.models import User
from app.modules.interviews.dependencies import get_interview_service
from app.modules.interviews.schemas import InterviewConfirmRequest, InterviewDetailResponse
from app.modules.interviews.service import InterviewService, build_interview_detail
from app.shared.exceptions import AppException

router = APIRouter(prefix="/careers/interviews", tags=["Careers"])


def _handle(exc: AppException) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/{interview_id}", response_model=InterviewDetailResponse)
def get_own_interview(
    interview_id: int,
    current_user: User = Depends(require_roles("candidate")),
    interview_service: InterviewService = Depends(get_interview_service),
) -> InterviewDetailResponse:
    try:
        return build_interview_detail(interview_service.get_own(current_user, interview_id))
    except AppException as exc:
        _handle(exc)


@router.post("/{interview_id}/confirm", response_model=InterviewDetailResponse)
def confirm_interview_slot(
    interview_id: int,
    payload: InterviewConfirmRequest,
    current_user: User = Depends(require_roles("candidate")),
    interview_service: InterviewService = Depends(get_interview_service),
) -> InterviewDetailResponse:
    try:
        interview = interview_service.confirm_slot(current_user, interview_id, payload.slot_id)
        return build_interview_detail(interview)
    except AppException as exc:
        _handle(exc)
