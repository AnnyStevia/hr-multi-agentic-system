from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.identity.hr_access import require_hr_staff
from app.modules.identity.models import User
from app.modules.interviews.dependencies import get_interview_service
from app.modules.interviews.schemas import (
    InterviewCompleteRequest,
    InterviewCreateRequest,
    InterviewDetailResponse,
    InterviewOutcomeRequest,
    InterviewSummary,
)
from app.modules.interviews.service import InterviewService, build_interview_detail, build_interview_summary
from app.shared.exceptions import AppException

router = APIRouter(prefix="/interviews", tags=["Interviews"])


def _handle(exc: AppException) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


def _detail(service: InterviewService, interview) -> InterviewDetailResponse:
    return build_interview_detail(
        interview,
        hired_employee_id=service.resolve_hired_employee_id(interview),
    )


def _summary(service: InterviewService, interview) -> InterviewSummary:
    return build_interview_summary(
        interview,
        hired_employee_id=service.resolve_hired_employee_id(interview),
    )


@router.get("/applications/{application_id}", response_model=list[InterviewSummary])
def list_application_interviews(
    application_id: int,
    _user: User = Depends(require_hr_staff("recruitment:read")),
    interview_service: InterviewService = Depends(get_interview_service),
) -> list[InterviewSummary]:
    try:
        return [
            _summary(interview_service, interview)
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
    current_user: User = Depends(require_hr_staff("recruitment:write")),
    interview_service: InterviewService = Depends(get_interview_service),
) -> InterviewDetailResponse:
    try:
        interview = interview_service.create_invitation(
            application_id,
            payload,
            created_by=current_user,
        )
        return _detail(interview_service, interview)
    except AppException as exc:
        _handle(exc)


@router.get("/{interview_id}", response_model=InterviewDetailResponse)
def get_interview(
    interview_id: int,
    _user: User = Depends(require_hr_staff("recruitment:read")),
    interview_service: InterviewService = Depends(get_interview_service),
) -> InterviewDetailResponse:
    try:
        return _detail(interview_service, interview_service.get_for_hr(interview_id))
    except AppException as exc:
        _handle(exc)


@router.patch("/{interview_id}/complete", response_model=InterviewDetailResponse)
def complete_interview(
    interview_id: int,
    payload: InterviewCompleteRequest,
    _user: User = Depends(require_hr_staff("recruitment:write")),
    interview_service: InterviewService = Depends(get_interview_service),
) -> InterviewDetailResponse:
    try:
        interview = interview_service.complete_interview(interview_id, payload.feedback)
        return _detail(interview_service, interview)
    except AppException as exc:
        _handle(exc)


@router.post("/{interview_id}/outcome", response_model=InterviewDetailResponse)
def record_interview_outcome(
    interview_id: int,
    payload: InterviewOutcomeRequest,
    _user: User = Depends(require_hr_staff("recruitment:write")),
    interview_service: InterviewService = Depends(get_interview_service),
) -> InterviewDetailResponse:
    try:
        interview = interview_service.record_outcome(interview_id, payload.outcome)
        return _detail(interview_service, interview)
    except AppException as exc:
        _handle(exc)
