from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.employees.dependencies import get_employee_service
from app.modules.employees.schemas import (
    EmployeeCreateRequest,
    EmployeeListResponse,
    EmployeeResponse,
    EmployeeUpdateRequest,
)
from app.modules.employees.service import EmployeeService, build_employee_response
from app.modules.identity.hr_access import require_hr_staff
from app.modules.identity.models import User
from app.shared.exceptions import AppException

router = APIRouter(prefix="/employees", tags=["Employees"])


def _handle(exc: AppException) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("", response_model=EmployeeListResponse)
def list_employees(
    status: str = Query(default="active"),
    department_id: int | None = Query(default=None),
    q: str | None = Query(default=None),
    _user: User = Depends(require_hr_staff("employees:read")),
    employee_service: EmployeeService = Depends(get_employee_service),
) -> EmployeeListResponse:
    try:
        rows, total = employee_service.list_employees(
            status=status,
            department_id=department_id,
            q=q,
        )
        return EmployeeListResponse(
            items=[build_employee_response(row) for row in rows],
            total=total,
        )
    except AppException as exc:
        _handle(exc)


@router.post("", response_model=EmployeeResponse, status_code=201)
def create_employee(
    payload: EmployeeCreateRequest,
    _user: User = Depends(require_hr_staff("employees:write")),
    employee_service: EmployeeService = Depends(get_employee_service),
) -> EmployeeResponse:
    try:
        return build_employee_response(employee_service.create_employee(payload))
    except AppException as exc:
        _handle(exc)


@router.get("/{employee_id}", response_model=EmployeeResponse)
def get_employee(
    employee_id: int,
    _user: User = Depends(require_hr_staff("employees:read")),
    employee_service: EmployeeService = Depends(get_employee_service),
) -> EmployeeResponse:
    try:
        return build_employee_response(employee_service.get_employee(employee_id))
    except AppException as exc:
        _handle(exc)


@router.patch("/{employee_id}", response_model=EmployeeResponse)
def update_employee(
    employee_id: int,
    payload: EmployeeUpdateRequest,
    _user: User = Depends(require_hr_staff("employees:write")),
    employee_service: EmployeeService = Depends(get_employee_service),
) -> EmployeeResponse:
    try:
        return build_employee_response(employee_service.update_employee(employee_id, payload))
    except AppException as exc:
        _handle(exc)


@router.patch("/{employee_id}/deactivate", response_model=EmployeeResponse)
def deactivate_employee(
    employee_id: int,
    _user: User = Depends(require_hr_staff("employees:write")),
    employee_service: EmployeeService = Depends(get_employee_service),
) -> EmployeeResponse:
    try:
        return build_employee_response(employee_service.deactivate_employee(employee_id))
    except AppException as exc:
        _handle(exc)


@router.post("/{employee_id}/convert-to-employee", response_model=EmployeeResponse)
def convert_intern_to_employee(
    employee_id: int,
    current_user: User = Depends(require_hr_staff("employees:write")),
    employee_service: EmployeeService = Depends(get_employee_service),
) -> EmployeeResponse:
    try:
        return build_employee_response(
            employee_service.convert_intern_to_employee(employee_id, current_user.id)
        )
    except AppException as exc:
        _handle(exc)
