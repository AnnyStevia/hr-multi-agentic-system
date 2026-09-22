"""Leave dual-approval resolution (manager + HR, availability-aware)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from sqlalchemy.orm import Session

from app.modules.employees.models import Employee
from app.modules.employees.repository import EmployeeRepository
from app.modules.identity.hr_access import list_admin_user_ids, list_hr_role_user_ids
from app.modules.identity.models import Role, User, UserRole
from app.modules.leave.models import LeaveApprovalStatus, LeaveRequest
from app.modules.leave.schemas import CurrentWorkStatus
from app.modules.leave.status import derive_current_work_status


class ApprovalActor(str, Enum):
    MANAGER = "manager"
    HR = "hr"
    ADMIN = "admin"


@dataclass(frozen=True)
class ApprovalRequirements:
    manager_required: bool
    hr_required: bool
    manager_satisfied: bool
    hr_satisfied: bool
    requester_is_hr: bool
    manager_available: bool
    hr_available: bool
    available_hr_user_ids: list[int]
    manager_user_id: int | None


def user_has_hr_role(db: Session, user_id: int) -> bool:
    row = (
        db.query(User.id)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .filter(User.id == user_id, Role.name == "hr")
        .first()
    )
    return row is not None


def is_employee_on_leave(db: Session, employee: Employee | None, *, as_of: date | None = None) -> bool:
    if employee is None:
        return False
    status = derive_current_work_status(db, employee.id, as_of=as_of)
    return status.current_work_status == CurrentWorkStatus.ON_LEAVE


def list_available_hr_approver_ids(
    db: Session,
    *,
    exclude_user_id: int | None,
    as_of: date | None = None,
) -> list[int]:
    """HR-role users who are not the requester and whose employee is not ON_LEAVE."""
    employees = EmployeeRepository(db)
    available: list[int] = []
    for user_id in list_hr_role_user_ids(db):
        if exclude_user_id is not None and user_id == exclude_user_id:
            continue
        employee = employees.get_by_user_id(user_id)
        if employee is not None and is_employee_on_leave(db, employee, as_of=as_of):
            continue
        # HR users without an employee profile still count as available approvers
        # (they can approve but cannot take leave themselves via /me/leave).
        available.append(user_id)
    return available


def resolve_requirements(
    db: Session,
    request: LeaveRequest,
    employee: Employee,
    *,
    as_of: date | None = None,
) -> ApprovalRequirements:
    requester_is_hr = employee.user_id is not None and user_has_hr_role(db, employee.user_id)

    manager: Employee | None = None
    manager_user_id: int | None = None
    if employee.manager_id is not None:
        manager = EmployeeRepository(db).get_by_id(employee.manager_id)
        if manager is not None:
            manager_user_id = manager.user_id

    manager_available = manager is not None and not is_employee_on_leave(db, manager, as_of=as_of)
    available_hr = list_available_hr_approver_ids(
        db, exclude_user_id=employee.user_id, as_of=as_of
    )
    hr_available = len(available_hr) > 0

    manager_satisfied = request.manager_approval == LeaveApprovalStatus.APPROVED
    hr_satisfied = request.hr_approval == LeaveApprovalStatus.APPROVED

    if requester_is_hr:
        # HR self-leave: manager alone when available; otherwise Admin only.
        manager_required = manager_available and not manager_satisfied
        hr_required = False
    else:
        # Normal employee: manager then HR, skipping unavailable stages.
        manager_required = manager_available and not manager_satisfied
        if manager_available and not manager_satisfied:
            # Ordered: HR waits until manager acts (unless manager unavailable).
            hr_required = False
        else:
            hr_required = hr_available and not hr_satisfied
            # If manager was needed historically but already approved / skipped,
            # and HR unavailable, manager approval alone finalizes when HR pool empty.
            if not hr_available and manager_satisfied:
                hr_required = False
            elif not hr_available and not manager_available and not manager_satisfied:
                # Both unavailable — only Admin can finalize.
                hr_required = False

    return ApprovalRequirements(
        manager_required=manager_required,
        hr_required=hr_required,
        manager_satisfied=manager_satisfied,
        hr_satisfied=hr_satisfied,
        requester_is_hr=requester_is_hr,
        manager_available=manager_available,
        hr_available=hr_available,
        available_hr_user_ids=available_hr,
        manager_user_id=manager_user_id,
    )


def classify_actor(
    db: Session,
    request: LeaveRequest,
    employee: Employee,
    actor_user_id: int,
) -> ApprovalActor | None:
    if employee.user_id is not None and employee.user_id == actor_user_id:
        return None

    if actor_user_id in set(list_admin_user_ids(db)):
        return ApprovalActor.ADMIN

    reviewer_employee = EmployeeRepository(db).get_by_user_id(actor_user_id)
    if (
        reviewer_employee is not None
        and employee.manager_id is not None
        and employee.manager_id == reviewer_employee.id
    ):
        return ApprovalActor.MANAGER

    if user_has_hr_role(db, actor_user_id):
        return ApprovalActor.HR

    return None


def would_finalize_after_manager(reqs: ApprovalRequirements) -> bool:
    """True when manager approval alone completes the request."""
    if reqs.requester_is_hr:
        return True
    return not reqs.hr_available


def would_finalize_after_hr(reqs: ApprovalRequirements) -> bool:
    return True
