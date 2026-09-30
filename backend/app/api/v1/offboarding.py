from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from app.modules.identity.dependencies import get_current_user
from app.modules.identity.hr_access import require_hr_staff
from app.modules.identity.models import User
from app.modules.offboarding.dependencies import (
    get_exit_interview_meeting_service,
    get_offboarding_service,
)
from app.modules.offboarding.meeting_runner import run_exit_interview_meeting_provision
from app.modules.offboarding.meeting_service import ExitInterviewMeetingService
from app.modules.offboarding.models import OffboardingStatus
from app.modules.offboarding.schemas import (
    ExitInterviewCompleteRequest,
    ExitInterviewCreateRequest,
    ExitInterviewEmployeeViewResponse,
    ExitInterviewResponse,
    ExitInterviewUpdateRequest,
    OffboardingClearanceCreateRequest,
    OffboardingClearanceEmployeeViewResponse,
    OffboardingClearanceItemResponse,
    OffboardingClearanceProgressResponse,
    OffboardingClearanceUpdateRequest,
    OffboardingCanCompleteResponse,
    OffboardingCreateRequest,
    OffboardingDetailResponse,
    OffboardingEmployeeViewResponse,
    OffboardingListItemResponse,
    OffboardingProgressResponse,
    OffboardingTaskCreateRequest,
    OffboardingTaskEmployeeViewResponse,
    OffboardingTaskResponse,
    OffboardingTaskUpdateRequest,
)
from app.modules.offboarding.service import (
    OffboardingService,
    build_clearance_item_response,
    build_detail_response,
    build_employee_clearance_response,
    build_employee_exit_interview_response,
    build_employee_task_response,
    build_employee_view_response,
    build_exit_interview_response,
    build_task_response,
)
from app.shared.exceptions import AppException

me_router = APIRouter(prefix="/me", tags=["Offboarding"])
router = APIRouter(prefix="/offboarding", tags=["Offboarding"])


def _handle(exc: AppException) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@me_router.get("/offboarding", response_model=list[OffboardingEmployeeViewResponse])
def list_my_offboarding(
    current_user: User = Depends(get_current_user),
    service: OffboardingService = Depends(get_offboarding_service),
) -> list[OffboardingEmployeeViewResponse]:
    try:
        return [
            build_employee_view_response(case)
            for case in service.list_for_user(current_user.id)
        ]
    except AppException as exc:
        _handle(exc)


@me_router.get("/offboarding/tasks", response_model=list[OffboardingTaskEmployeeViewResponse])
def list_my_offboarding_tasks(
    current_user: User = Depends(get_current_user),
    service: OffboardingService = Depends(get_offboarding_service),
) -> list[OffboardingTaskEmployeeViewResponse]:
    try:
        return [
            build_employee_task_response(task)
            for task in service.list_tasks_for_user(current_user.id)
        ]
    except AppException as exc:
        _handle(exc)


@me_router.post(
    "/offboarding/tasks/{task_id}/start",
    response_model=OffboardingTaskEmployeeViewResponse,
)
def start_my_offboarding_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    service: OffboardingService = Depends(get_offboarding_service),
) -> OffboardingTaskEmployeeViewResponse:
    try:
        return build_employee_task_response(
            service.start_task_for_user(current_user.id, task_id)
        )
    except AppException as exc:
        _handle(exc)


@me_router.post(
    "/offboarding/tasks/{task_id}/complete",
    response_model=OffboardingTaskEmployeeViewResponse,
)
def complete_my_offboarding_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    service: OffboardingService = Depends(get_offboarding_service),
) -> OffboardingTaskEmployeeViewResponse:
    try:
        return build_employee_task_response(
            service.complete_task_for_user(current_user.id, task_id, current_user)
        )
    except AppException as exc:
        _handle(exc)


@me_router.get(
    "/offboarding/clearance",
    response_model=list[OffboardingClearanceEmployeeViewResponse],
)
def list_my_offboarding_clearance(
    current_user: User = Depends(get_current_user),
    service: OffboardingService = Depends(get_offboarding_service),
) -> list[OffboardingClearanceEmployeeViewResponse]:
    try:
        return [
            build_employee_clearance_response(item)
            for item in service.list_clearance_for_user(current_user.id)
        ]
    except AppException as exc:
        _handle(exc)


@me_router.get(
    "/offboarding/exit-interview",
    response_model=ExitInterviewEmployeeViewResponse | None,
)
def get_my_exit_interview(
    current_user: User = Depends(get_current_user),
    service: OffboardingService = Depends(get_offboarding_service),
) -> ExitInterviewEmployeeViewResponse | None:
    try:
        interview = service.get_exit_interview_for_user(current_user.id)
        if interview is None:
            return None
        return build_employee_exit_interview_response(interview)
    except AppException as exc:
        _handle(exc)


@router.post("", response_model=OffboardingDetailResponse, status_code=status.HTTP_201_CREATED)
def create_offboarding(
    payload: OffboardingCreateRequest,
    current_user: User = Depends(require_hr_staff("offboarding:write")),
    service: OffboardingService = Depends(get_offboarding_service),
) -> OffboardingDetailResponse:
    try:
        case = service.create_for_hr(current_user, payload)
        return build_detail_response(service.get_for_hr(case.id))
    except AppException as exc:
        _handle(exc)


@router.get("", response_model=list[OffboardingListItemResponse])
def list_offboarding(
    status_filter: OffboardingStatus | None = Query(None, alias="status"),
    employee_id: int | None = Query(None),
    _user: User = Depends(require_hr_staff("offboarding:read")),
    service: OffboardingService = Depends(get_offboarding_service),
) -> list[OffboardingListItemResponse]:
    return service.list_for_hr(status=status_filter, employee_id=employee_id)


@router.get("/{case_id}", response_model=OffboardingDetailResponse)
def get_offboarding(
    case_id: int,
    _user: User = Depends(require_hr_staff("offboarding:read")),
    service: OffboardingService = Depends(get_offboarding_service),
) -> OffboardingDetailResponse:
    try:
        return build_detail_response(service.get_for_hr(case_id))
    except AppException as exc:
        _handle(exc)


@router.get("/{case_id}/progress", response_model=OffboardingProgressResponse)
def get_offboarding_progress(
    case_id: int,
    _user: User = Depends(require_hr_staff("offboarding:read")),
    service: OffboardingService = Depends(get_offboarding_service),
) -> OffboardingProgressResponse:
    try:
        return service.get_progress(case_id)
    except AppException as exc:
        _handle(exc)


@router.get("/{case_id}/tasks", response_model=list[OffboardingTaskResponse])
def list_offboarding_tasks(
    case_id: int,
    _user: User = Depends(require_hr_staff("offboarding:read")),
    service: OffboardingService = Depends(get_offboarding_service),
) -> list[OffboardingTaskResponse]:
    try:
        return [build_task_response(task) for task in service.list_tasks_for_hr(case_id)]
    except AppException as exc:
        _handle(exc)


@router.post(
    "/{case_id}/tasks",
    response_model=OffboardingTaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_offboarding_task(
    case_id: int,
    payload: OffboardingTaskCreateRequest,
    _user: User = Depends(require_hr_staff("offboarding:write")),
    service: OffboardingService = Depends(get_offboarding_service),
) -> OffboardingTaskResponse:
    try:
        task = service.create_task_for_hr(case_id, payload)
        loaded = service.repository.get_task_for_case(case_id, task.id)
        assert loaded is not None
        return build_task_response(loaded)
    except AppException as exc:
        _handle(exc)


@router.patch("/{case_id}/tasks/{task_id}", response_model=OffboardingTaskResponse)
def update_offboarding_task(
    case_id: int,
    task_id: int,
    payload: OffboardingTaskUpdateRequest,
    _user: User = Depends(require_hr_staff("offboarding:write")),
    service: OffboardingService = Depends(get_offboarding_service),
) -> OffboardingTaskResponse:
    try:
        task = service.update_task_for_hr(case_id, task_id, payload)
        loaded = service.repository.get_task_for_case(case_id, task.id)
        assert loaded is not None
        return build_task_response(loaded)
    except AppException as exc:
        _handle(exc)


@router.post("/{case_id}/tasks/{task_id}/start", response_model=OffboardingTaskResponse)
def start_offboarding_task(
    case_id: int,
    task_id: int,
    _user: User = Depends(require_hr_staff("offboarding:write")),
    service: OffboardingService = Depends(get_offboarding_service),
) -> OffboardingTaskResponse:
    try:
        return build_task_response(service.start_task_for_hr(case_id, task_id))
    except AppException as exc:
        _handle(exc)


@router.post("/{case_id}/tasks/{task_id}/complete", response_model=OffboardingTaskResponse)
def complete_offboarding_task(
    case_id: int,
    task_id: int,
    current_user: User = Depends(require_hr_staff("offboarding:write")),
    service: OffboardingService = Depends(get_offboarding_service),
) -> OffboardingTaskResponse:
    try:
        return build_task_response(
            service.complete_task_for_hr(case_id, task_id, current_user)
        )
    except AppException as exc:
        _handle(exc)


@router.post("/{case_id}/tasks/{task_id}/skip", response_model=OffboardingTaskResponse)
def skip_offboarding_task(
    case_id: int,
    task_id: int,
    _user: User = Depends(require_hr_staff("offboarding:write")),
    service: OffboardingService = Depends(get_offboarding_service),
) -> OffboardingTaskResponse:
    try:
        return build_task_response(service.skip_task_for_hr(case_id, task_id))
    except AppException as exc:
        _handle(exc)


@router.post("/{case_id}/tasks/{task_id}/reopen", response_model=OffboardingTaskResponse)
def reopen_offboarding_task(
    case_id: int,
    task_id: int,
    _user: User = Depends(require_hr_staff("offboarding:write")),
    service: OffboardingService = Depends(get_offboarding_service),
) -> OffboardingTaskResponse:
    try:
        return build_task_response(service.reopen_task_for_hr(case_id, task_id))
    except AppException as exc:
        _handle(exc)


@router.get("/{case_id}/clearance", response_model=list[OffboardingClearanceItemResponse])
def list_offboarding_clearance(
    case_id: int,
    _user: User = Depends(require_hr_staff("offboarding:read")),
    service: OffboardingService = Depends(get_offboarding_service),
) -> list[OffboardingClearanceItemResponse]:
    try:
        return [
            build_clearance_item_response(item)
            for item in service.list_clearance_for_hr(case_id)
        ]
    except AppException as exc:
        _handle(exc)


@router.get(
    "/{case_id}/clearance/progress",
    response_model=OffboardingClearanceProgressResponse,
)
def get_offboarding_clearance_progress(
    case_id: int,
    _user: User = Depends(require_hr_staff("offboarding:read")),
    service: OffboardingService = Depends(get_offboarding_service),
) -> OffboardingClearanceProgressResponse:
    try:
        return service.get_clearance_progress(case_id)
    except AppException as exc:
        _handle(exc)


@router.post(
    "/{case_id}/clearance",
    response_model=OffboardingClearanceItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_offboarding_clearance_item(
    case_id: int,
    payload: OffboardingClearanceCreateRequest,
    _user: User = Depends(require_hr_staff("offboarding:write")),
    service: OffboardingService = Depends(get_offboarding_service),
) -> OffboardingClearanceItemResponse:
    try:
        item = service.create_clearance_item_for_hr(case_id, payload)
        loaded = service.repository.get_clearance_for_case(case_id, item.id)
        assert loaded is not None
        return build_clearance_item_response(loaded)
    except AppException as exc:
        _handle(exc)


@router.patch(
    "/{case_id}/clearance/{item_id}",
    response_model=OffboardingClearanceItemResponse,
)
def update_offboarding_clearance_item(
    case_id: int,
    item_id: int,
    payload: OffboardingClearanceUpdateRequest,
    current_user: User = Depends(require_hr_staff("offboarding:write")),
    service: OffboardingService = Depends(get_offboarding_service),
) -> OffboardingClearanceItemResponse:
    try:
        item = service.update_clearance_item_for_hr(
            case_id, item_id, payload, current_user
        )
        loaded = service.repository.get_clearance_for_case(case_id, item.id)
        assert loaded is not None
        return build_clearance_item_response(loaded)
    except AppException as exc:
        _handle(exc)


@router.get(
    "/{case_id}/exit-interview",
    response_model=ExitInterviewResponse | None,
)
def get_exit_interview(
    case_id: int,
    _user: User = Depends(require_hr_staff("offboarding:read")),
    service: OffboardingService = Depends(get_offboarding_service),
) -> ExitInterviewResponse | None:
    try:
        interview = service.get_exit_interview_for_hr(case_id)
        if interview is None:
            return None
        return build_exit_interview_response(interview)
    except AppException as exc:
        _handle(exc)


@router.post(
    "/{case_id}/exit-interview",
    response_model=ExitInterviewResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_exit_interview(
    case_id: int,
    payload: ExitInterviewCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_hr_staff("offboarding:write")),
    service: OffboardingService = Depends(get_offboarding_service),
) -> ExitInterviewResponse:
    try:
        interview = service.create_exit_interview_for_hr(case_id, current_user, payload)
        if interview.meeting_url is None:
            background_tasks.add_task(
                run_exit_interview_meeting_provision, interview.id
            )
        return build_exit_interview_response(interview)
    except AppException as exc:
        _handle(exc)


@router.patch("/{case_id}/exit-interview", response_model=ExitInterviewResponse)
def update_exit_interview(
    case_id: int,
    payload: ExitInterviewUpdateRequest,
    background_tasks: BackgroundTasks,
    _user: User = Depends(require_hr_staff("offboarding:write")),
    service: OffboardingService = Depends(get_offboarding_service),
) -> ExitInterviewResponse:
    try:
        interview = service.update_exit_interview_for_hr(case_id, payload)
        if interview.status.value == "scheduled" and interview.meeting_url is None:
            background_tasks.add_task(
                run_exit_interview_meeting_provision, interview.id
            )
        return build_exit_interview_response(interview)
    except AppException as exc:
        _handle(exc)


@router.post(
    "/{case_id}/exit-interview/complete",
    response_model=ExitInterviewResponse,
)
def complete_exit_interview(
    case_id: int,
    payload: ExitInterviewCompleteRequest,
    _user: User = Depends(require_hr_staff("offboarding:write")),
    service: OffboardingService = Depends(get_offboarding_service),
) -> ExitInterviewResponse:
    try:
        return build_exit_interview_response(
            service.complete_exit_interview_for_hr(case_id, payload)
        )
    except AppException as exc:
        _handle(exc)


@router.post(
    "/{case_id}/exit-interview/cancel",
    response_model=ExitInterviewResponse,
)
def cancel_exit_interview(
    case_id: int,
    _user: User = Depends(require_hr_staff("offboarding:write")),
    service: OffboardingService = Depends(get_offboarding_service),
) -> ExitInterviewResponse:
    try:
        return build_exit_interview_response(
            service.cancel_exit_interview_for_hr(case_id)
        )
    except AppException as exc:
        _handle(exc)


@router.post(
    "/{case_id}/exit-interview/meeting",
    response_model=ExitInterviewResponse,
)
def ensure_exit_interview_meeting(
    case_id: int,
    _user: User = Depends(require_hr_staff("offboarding:write")),
    service: OffboardingService = Depends(get_offboarding_service),
    meeting_service: ExitInterviewMeetingService = Depends(
        get_exit_interview_meeting_service
    ),
) -> ExitInterviewResponse:
    try:
        interview = service.get_exit_interview_for_hr(case_id)
        if interview is None:
            raise AppException("Exit interview not found", status_code=404)
        ensured = meeting_service.ensure_meeting(interview.id)
        loaded = service.repository.get_exit_interview_by_id(ensured.id)
        assert loaded is not None
        return build_exit_interview_response(loaded)
    except AppException as exc:
        _handle(exc)


@router.post("/{case_id}/start", response_model=OffboardingDetailResponse)
def start_offboarding(
    case_id: int,
    _user: User = Depends(require_hr_staff("offboarding:write")),
    service: OffboardingService = Depends(get_offboarding_service),
) -> OffboardingDetailResponse:
    try:
        return build_detail_response(service.start(case_id))
    except AppException as exc:
        _handle(exc)


@router.post("/{case_id}/pending-clearance", response_model=OffboardingDetailResponse)
def pending_clearance_offboarding(
    case_id: int,
    _user: User = Depends(require_hr_staff("offboarding:write")),
    service: OffboardingService = Depends(get_offboarding_service),
) -> OffboardingDetailResponse:
    try:
        return build_detail_response(service.move_to_pending_clearance(case_id))
    except AppException as exc:
        _handle(exc)


@router.get("/{case_id}/can-complete", response_model=OffboardingCanCompleteResponse)
def get_offboarding_can_complete(
    case_id: int,
    _user: User = Depends(require_hr_staff("offboarding:read")),
    service: OffboardingService = Depends(get_offboarding_service),
) -> OffboardingCanCompleteResponse:
    try:
        can_complete, blockers = service.can_complete(case_id)
        return OffboardingCanCompleteResponse(
            offboarding_case_id=case_id,
            can_complete=can_complete,
            blockers=blockers,
        )
    except AppException as exc:
        _handle(exc)


@router.post("/{case_id}/complete", response_model=OffboardingDetailResponse)
def complete_offboarding(
    case_id: int,
    _user: User = Depends(require_hr_staff("offboarding:write")),
    service: OffboardingService = Depends(get_offboarding_service),
) -> OffboardingDetailResponse:
    try:
        return build_detail_response(service.complete(case_id))
    except AppException as exc:
        _handle(exc)


@router.post("/{case_id}/cancel", response_model=OffboardingDetailResponse)
def cancel_offboarding(
    case_id: int,
    _user: User = Depends(require_hr_staff("offboarding:write")),
    service: OffboardingService = Depends(get_offboarding_service),
) -> OffboardingDetailResponse:
    try:
        return build_detail_response(service.cancel(case_id))
    except AppException as exc:
        _handle(exc)
