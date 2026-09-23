from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.modules.identity.dependencies import get_current_user
from app.modules.identity.hr_access import require_hr_staff
from app.modules.identity.models import User
from app.modules.onboarding.dependencies import (
    get_onboarding_service,
    require_employee_access_cleared,
)
from app.modules.onboarding.schemas import (
    OnboardingListItemResponse,
    OnboardingProgressResponse,
    OnboardingResponse,
    OnboardingTaskCreateRequest,
    OnboardingTaskResponse,
    OnboardingTaskTemplateCreateRequest,
    OnboardingTaskTemplateResponse,
    OnboardingTaskTemplateUpdateRequest,
    OnboardingTaskUpdateRequest,
)
from app.modules.onboarding.service import (
    OnboardingService,
    build_onboarding_response,
    build_onboarding_task_response,
    build_template_response,
)
from app.shared.exceptions import AppException

me_router = APIRouter(prefix="/me", tags=["Onboarding"])
router = APIRouter(prefix="/onboarding", tags=["Onboarding"])
employee_onboarding_router = APIRouter(prefix="/employees", tags=["Onboarding"])


def _handle(exc: AppException) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/task-templates", response_model=list[OnboardingTaskTemplateResponse])
def list_task_templates(
    active_only: bool = Query(default=False),
    _user: User = Depends(require_hr_staff("onboarding:read")),
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
) -> list[OnboardingTaskTemplateResponse]:
    return [
        build_template_response(item)
        for item in onboarding_service.list_templates(active_only=active_only)
    ]


@router.post(
    "/task-templates",
    response_model=OnboardingTaskTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_task_template(
    payload: OnboardingTaskTemplateCreateRequest,
    _user: User = Depends(require_hr_staff("onboarding:write")),
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingTaskTemplateResponse:
    try:
        return build_template_response(onboarding_service.create_template(payload))
    except AppException as exc:
        _handle(exc)


@router.get("/task-templates/{template_id}", response_model=OnboardingTaskTemplateResponse)
def get_task_template(
    template_id: int,
    _user: User = Depends(require_hr_staff("onboarding:read")),
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingTaskTemplateResponse:
    try:
        return build_template_response(onboarding_service.get_template(template_id))
    except AppException as exc:
        _handle(exc)


@router.patch("/task-templates/{template_id}", response_model=OnboardingTaskTemplateResponse)
def update_task_template(
    template_id: int,
    payload: OnboardingTaskTemplateUpdateRequest,
    _user: User = Depends(require_hr_staff("onboarding:write")),
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingTaskTemplateResponse:
    try:
        return build_template_response(onboarding_service.update_template(template_id, payload))
    except AppException as exc:
        _handle(exc)


@router.delete("/task-templates/{template_id}")
def delete_task_template(
    template_id: int,
    _user: User = Depends(require_hr_staff("onboarding:write")),
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
):
    try:
        result = onboarding_service.delete_template(template_id)
        if result is None:
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        return build_template_response(result)
    except AppException as exc:
        _handle(exc)


@me_router.get("/onboarding", response_model=OnboardingResponse)
def get_my_onboarding(
    current_user: User = Depends(get_current_user),
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingResponse:
    try:
        return build_onboarding_response(onboarding_service.get_for_employee_user(current_user.id))
    except AppException as exc:
        _handle(exc)


@me_router.get("/onboarding/progress", response_model=OnboardingProgressResponse)
def get_my_onboarding_progress(
    current_user: User = Depends(get_current_user),
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingProgressResponse:
    try:
        return onboarding_service.get_progress_for_employee_user(current_user.id)
    except AppException as exc:
        _handle(exc)


@me_router.get("/onboarding/tasks", response_model=list[OnboardingTaskResponse])
def list_my_onboarding_tasks(
    current_user: User = Depends(get_current_user),
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
) -> list[OnboardingTaskResponse]:
    try:
        tasks = onboarding_service.list_tasks_for_employee_user(current_user.id)
        return [build_onboarding_task_response(task) for task in tasks]
    except AppException as exc:
        _handle(exc)


@me_router.patch("/onboarding/tasks/{task_id}/complete", response_model=OnboardingTaskResponse)
def complete_my_onboarding_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingTaskResponse:
    """Legacy alias: only acknowledgement tasks are allowed."""
    try:
        task = onboarding_service.complete_task_for_employee_user(current_user.id, task_id)
        return build_onboarding_task_response(task)
    except AppException as exc:
        _handle(exc)


@me_router.patch("/onboarding/tasks/{task_id}/acknowledge", response_model=OnboardingTaskResponse)
def acknowledge_my_onboarding_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingTaskResponse:
    try:
        task = onboarding_service.acknowledge_task_for_employee(current_user.id, task_id)
        return build_onboarding_task_response(task)
    except AppException as exc:
        _handle(exc)


@me_router.get("/employee-home")
def get_employee_home(
    _user: User = Depends(require_employee_access_cleared),
) -> dict[str, str]:
    return {"status": "ok", "message": "Employee home access granted"}


@router.get("", response_model=list[OnboardingListItemResponse])
def list_onboardings(
    _user: User = Depends(require_hr_staff("onboarding:read")),
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
) -> list[OnboardingListItemResponse]:
    return onboarding_service.list_for_hr()


@router.get("/{onboarding_id}/progress", response_model=OnboardingProgressResponse)
def get_onboarding_progress(
    onboarding_id: int,
    _user: User = Depends(require_hr_staff("onboarding:read")),
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingProgressResponse:
    try:
        return onboarding_service.get_progress_for_hr(onboarding_id)
    except AppException as exc:
        _handle(exc)


@router.post("/{onboarding_id}/complete", response_model=OnboardingResponse)
def complete_onboarding(
    onboarding_id: int,
    _user: User = Depends(require_hr_staff("onboarding:write")),
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingResponse:
    try:
        return build_onboarding_response(onboarding_service.complete_for_hr(onboarding_id))
    except AppException as exc:
        _handle(exc)


@router.patch("/tasks/{task_id}", response_model=OnboardingTaskResponse)
def update_onboarding_task(
    task_id: int,
    payload: OnboardingTaskUpdateRequest,
    _user: User = Depends(require_hr_staff("onboarding:write")),
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingTaskResponse:
    try:
        return build_onboarding_task_response(onboarding_service.update_task(task_id, payload))
    except AppException as exc:
        _handle(exc)


@router.patch("/tasks/{task_id}/complete", response_model=OnboardingTaskResponse)
def complete_manual_onboarding_task(
    task_id: int,
    _user: User = Depends(require_hr_staff("onboarding:write")),
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingTaskResponse:
    try:
        return build_onboarding_task_response(
            onboarding_service.complete_manual_task_for_hr(task_id)
        )
    except AppException as exc:
        _handle(exc)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_onboarding_task(
    task_id: int,
    _user: User = Depends(require_hr_staff("onboarding:write")),
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
) -> Response:
    try:
        onboarding_service.delete_task(task_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except AppException as exc:
        _handle(exc)


@router.get("/{onboarding_id}/tasks", response_model=list[OnboardingTaskResponse])
def list_onboarding_tasks(
    onboarding_id: int,
    _user: User = Depends(require_hr_staff("onboarding:read")),
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
) -> list[OnboardingTaskResponse]:
    try:
        tasks = onboarding_service.list_tasks_for_hr(onboarding_id)
        return [build_onboarding_task_response(task) for task in tasks]
    except AppException as exc:
        _handle(exc)


@router.post(
    "/{onboarding_id}/tasks",
    response_model=OnboardingTaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_onboarding_task(
    onboarding_id: int,
    payload: OnboardingTaskCreateRequest,
    _user: User = Depends(require_hr_staff("onboarding:write")),
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingTaskResponse:
    try:
        return build_onboarding_task_response(
            onboarding_service.create_task(onboarding_id, payload)
        )
    except AppException as exc:
        _handle(exc)


@router.get("/{onboarding_id}", response_model=OnboardingResponse)
def get_onboarding(
    onboarding_id: int,
    _user: User = Depends(require_hr_staff("onboarding:read")),
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingResponse:
    try:
        return build_onboarding_response(onboarding_service.get_for_hr(onboarding_id))
    except AppException as exc:
        _handle(exc)


@employee_onboarding_router.get("/{employee_id}/onboarding", response_model=OnboardingResponse)
def get_employee_onboarding(
    employee_id: int,
    _user: User = Depends(require_hr_staff("onboarding:read")),
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingResponse:
    try:
        return build_onboarding_response(
            onboarding_service.get_by_employee_id_for_hr(employee_id)
        )
    except AppException as exc:
        _handle(exc)
