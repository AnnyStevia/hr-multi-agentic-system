from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import User
from app.modules.interviews.dependencies import get_interview_service
from app.modules.interviews.schemas import (
    InterviewCompleteRequest,
    InterviewDetailResponse,
    InterviewProposeSlotsRequest,
    InterviewSummary,
)
from app.modules.interviews.service import InterviewService, build_interview_detail, build_interview_summary
from app.shared.exceptions import AppException

router = APIRouter(prefix="/me/interviews", tags=["My Interviews"])


def _handle(exc: AppException) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


def _actor_employee_id(service: InterviewService, user: User) -> int | None:
    employee = service.repository.get_employee_for_user(user.id)
    return employee.id if employee else None


@router.get("", response_model=list[InterviewSummary])
def list_my_interviews(
    current_user: User = Depends(get_current_user),
    interview_service: InterviewService = Depends(get_interview_service),
) -> list[InterviewSummary]:
    try:
        actor_id = _actor_employee_id(interview_service, current_user)
        return [
            build_interview_summary(
                interview,
                hired_employee_id=interview_service.resolve_hired_employee_id(interview),
                include_evaluation=True,
                actor_employee_id=actor_id,
            )
            for interview in interview_service.list_for_employee_user(current_user)
        ]
    except AppException as exc:
        _handle(exc)


@router.get("/{interview_id}", response_model=InterviewDetailResponse)
def get_my_interview(
    interview_id: int,
    current_user: User = Depends(get_current_user),
    interview_service: InterviewService = Depends(get_interview_service),
) -> InterviewDetailResponse:
    try:
        interview = interview_service.get_for_panel_member(current_user, interview_id)
        actor_id = _actor_employee_id(interview_service, current_user)
        return build_interview_detail(
            interview,
            hired_employee_id=interview_service.resolve_hired_employee_id(interview),
            include_evaluation=True,
            actor_employee_id=actor_id,
        )
    except AppException as exc:
        _handle(exc)


@router.post("/{interview_id}/slots", response_model=InterviewDetailResponse)
def propose_my_interview_slots(
    interview_id: int,
    payload: InterviewProposeSlotsRequest,
    current_user: User = Depends(get_current_user),
    interview_service: InterviewService = Depends(get_interview_service),
) -> InterviewDetailResponse:
    try:
        interview = interview_service.propose_slots(
            interview_id,
            payload.slots,
            actor=current_user,
        )
        actor_id = _actor_employee_id(interview_service, current_user)
        return build_interview_detail(
            interview,
            hired_employee_id=interview_service.resolve_hired_employee_id(interview),
            include_evaluation=True,
            actor_employee_id=actor_id,
        )
    except AppException as exc:
        _handle(exc)


@router.post(
    "/{interview_id}/complete",
    response_model=InterviewDetailResponse,
    status_code=status.HTTP_200_OK,
)
def complete_my_interview(
    interview_id: int,
    payload: InterviewCompleteRequest,
    current_user: User = Depends(get_current_user),
    interview_service: InterviewService = Depends(get_interview_service),
) -> InterviewDetailResponse:
    try:
        interview = interview_service.complete_interview(
            interview_id,
            payload,
            actor=current_user,
        )
        actor_id = _actor_employee_id(interview_service, current_user)
        return build_interview_detail(
            interview,
            hired_employee_id=interview_service.resolve_hired_employee_id(interview),
            include_evaluation=True,
            actor_employee_id=actor_id,
        )
    except AppException as exc:
        _handle(exc)
