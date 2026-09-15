from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.employees.dependencies import get_department_service
from app.modules.employees.schemas import (
    DepartmentCreateRequest,
    DepartmentResponse,
    DepartmentUpdateRequest,
)
from app.modules.employees.service import DepartmentService
from app.modules.identity.hr_access import require_hr_staff
from app.modules.identity.models import User
from app.shared.exceptions import AppException

router = APIRouter(prefix="/departments", tags=["Departments"])


def _handle(exc: AppException) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("", response_model=list[DepartmentResponse])
def list_departments(
    status: str = Query(default="all"),
    _user: User = Depends(require_hr_staff("employees:read")),
    department_service: DepartmentService = Depends(get_department_service),
) -> list[DepartmentResponse]:
    try:
        return department_service.list_departments(status)
    except AppException as exc:
        _handle(exc)


@router.post("", response_model=DepartmentResponse, status_code=201)
def create_department(
    payload: DepartmentCreateRequest,
    _user: User = Depends(require_hr_staff("employees:write")),
    department_service: DepartmentService = Depends(get_department_service),
) -> DepartmentResponse:
    try:
        return department_service.create_department(payload)
    except AppException as exc:
        _handle(exc)


@router.get("/{department_id}", response_model=DepartmentResponse)
def get_department(
    department_id: int,
    _user: User = Depends(require_hr_staff("employees:read")),
    department_service: DepartmentService = Depends(get_department_service),
) -> DepartmentResponse:
    try:
        return department_service.get_department(department_id)
    except AppException as exc:
        _handle(exc)


@router.patch("/{department_id}", response_model=DepartmentResponse)
def update_department(
    department_id: int,
    payload: DepartmentUpdateRequest,
    _user: User = Depends(require_hr_staff("employees:write")),
    department_service: DepartmentService = Depends(get_department_service),
) -> DepartmentResponse:
    try:
        return department_service.update_department(department_id, payload)
    except AppException as exc:
        _handle(exc)


@router.patch("/{department_id}/deactivate", response_model=DepartmentResponse)
def deactivate_department(
    department_id: int,
    _user: User = Depends(require_hr_staff("employees:write")),
    department_service: DepartmentService = Depends(get_department_service),
) -> DepartmentResponse:
    try:
        return department_service.deactivate_department(department_id)
    except AppException as exc:
        _handle(exc)
