from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.modules.identity.models import User
from app.modules.interviews.dependencies import get_interview_service
from app.modules.interviews.meeting_runner import run_interview_meeting_provision
from app.modules.interviews.schemas import InterviewConfirmRequest, InterviewDetailResponse
from app.modules.interviews.service import InterviewService, build_interview_detail
from app.modules.onboarding.dependencies import require_careers_access
from app.shared.exceptions import AppException

router = APIRouter(prefix="/careers/interviews", tags=["Careers"])


def _handle(exc: AppException) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


def _candidate_detail(interview) -> InterviewDetailResponse:
    return build_interview_detail(interview, include_evaluation=False)


@router.get("/{interview_id}", response_model=InterviewDetailResponse)
def get_own_interview(
    interview_id: int,
    current_user: User = Depends(require_careers_access),
    interview_service: InterviewService = Depends(get_interview_service),
) -> InterviewDetailResponse:
    try:
        return _candidate_detail(interview_service.get_own(current_user, interview_id))
    except AppException as exc:
        _handle(exc)


@router.post("/{interview_id}/confirm", response_model=InterviewDetailResponse)
def confirm_interview_slot(
    interview_id: int,
    payload: InterviewConfirmRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_careers_access),
    interview_service: InterviewService = Depends(get_interview_service),
) -> InterviewDetailResponse:
    try:
        interview = interview_service.confirm_slot(current_user, interview_id, payload.slot_id)
        if interview.meeting_url is None:
            background_tasks.add_task(run_interview_meeting_provision, interview.id)
        return _candidate_detail(interview)
    except AppException as exc:
        _handle(exc)
