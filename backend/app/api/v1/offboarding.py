from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.modules.identity.dependencies import get_current_user
from app.modules.identity.hr_access import require_hr_staff
from app.modules.identity.models import User
from app.modules.offboarding.dependencies import get_offboarding_service
from app.modules.offboarding.models import OffboardingStatus
from app.modules.offboarding.schemas import (
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
    build_detail_response,
    build_employee_task_response,
    build_employee_view_response,
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
