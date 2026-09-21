from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.employees.dependencies import get_employee_service
from app.modules.employees.schemas import (
    DirectoryResponse,
    EmployeeOrganizationResponse,
    HierarchyResponse,
)
from app.modules.employees.service import EmployeeService
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.hr_access import HR_STAFF_ROLE_NAMES, require_hr_staff
from app.modules.identity.models import User
from app.shared.exceptions import AppException
from app.shared.storage import get_storage_service
from app.shared.storage.base import StorageService

org_router = APIRouter(prefix="/organization", tags=["Organization"])
me_org_router = APIRouter(prefix="/me", tags=["Organization"])
employees_org_router = APIRouter(prefix="/employees", tags=["Organization"])


def _handle(exc: AppException) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


def _require_org_viewer(user: User = Depends(get_current_user)) -> User:
    roles = {user_role.role.name for user_role in user.user_roles}
    if HR_STAFF_ROLE_NAMES & roles or "employee" in roles:
        return user
    raise HTTPException(status_code=403, detail="Requires employee or HR access")


@me_org_router.get("/organization", response_model=EmployeeOrganizationResponse)
def get_my_organization(
    current_user: User = Depends(get_current_user),
    employee_service: EmployeeService = Depends(get_employee_service),
) -> EmployeeOrganizationResponse:
    try:
        employee = employee_service.get_by_user_id(current_user.id)
        if employee is None:
            raise AppException("Employee profile not found", status_code=404)
        return employee_service.get_organization(employee.id)
    except AppException as exc:
        _handle(exc)


@employees_org_router.get("/{employee_id}/organization", response_model=EmployeeOrganizationResponse)
def get_employee_organization(
    employee_id: int,
    _user: User = Depends(require_hr_staff("employees:read")),
    employee_service: EmployeeService = Depends(get_employee_service),
) -> EmployeeOrganizationResponse:
    try:
        return employee_service.get_organization(employee_id)
    except AppException as exc:
        _handle(exc)


@org_router.get("/hierarchy", response_model=HierarchyResponse)
def get_organization_hierarchy(
    _user: User = Depends(_require_org_viewer),
    employee_service: EmployeeService = Depends(get_employee_service),
) -> HierarchyResponse:
    try:
        return employee_service.get_hierarchy()
    except AppException as exc:
        _handle(exc)


@org_router.get("/directory", response_model=DirectoryResponse)
def get_organization_directory(
    q: str | None = Query(default=None),
    _user: User = Depends(_require_org_viewer),
    employee_service: EmployeeService = Depends(get_employee_service),
    storage: StorageService = Depends(get_storage_service),
) -> DirectoryResponse:
    try:
        return employee_service.get_directory(q=q, storage=storage)
    except AppException as exc:
        _handle(exc)
