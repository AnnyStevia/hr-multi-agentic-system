from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.ai.core.context.models import AIExecutionContext
from app.core.database import get_db
from app.modules.employees.repository import EmployeeRepository
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import User


def build_ai_execution_context(
    user: User,
    *,
    employees: EmployeeRepository,
) -> AIExecutionContext:
    """Build AI context solely from the authenticated user and linked records.

    Identity fields (user_id, roles, employee_id, candidate_id) are never taken
    from LLM messages or client claims—only from ``user`` and repository lookup.
    """
    role_names: set[str] = set()
    permission_names: set[str] = set()
    for user_role in user.user_roles:
        role = user_role.role
        role_names.add(role.name)
        for role_perm in role.role_permissions:
            permission_names.add(role_perm.permission.name)

    employee = employees.get_by_user_id(user.id)
    candidate = user.candidate_profile

    return AIExecutionContext(
        user_id=user.id,
        role_names=frozenset(role_names),
        permission_names=frozenset(permission_names),
        employee_id=employee.id if employee is not None else None,
        candidate_id=candidate.id if candidate is not None else None,
    )


def get_ai_execution_context(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AIExecutionContext:
    """FastAPI dependency: authenticated user → AIExecutionContext."""
    return build_ai_execution_context(
        current_user,
        employees=EmployeeRepository(db),
    )
