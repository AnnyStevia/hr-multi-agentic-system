from datetime import date
import inspect

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.ai.core.context import (
    AIExecutionContext,
    build_ai_execution_context,
    get_ai_execution_context,
)
from app.core.database import get_db
from app.modules.employees.models import Employee, EmploymentStatus
from app.modules.employees.repository import EmployeeRepository
from app.modules.identity.models import User
from app.modules.identity.service import AuthService
from app.tests.helpers import auth_header, create_candidate_user, create_user_with_role


def _reload_user(db_session, user_id: int) -> User:
    user = AuthService(db_session).get_user_by_id(user_id)
    assert user is not None
    return user


def _link_employee(
    db_session,
    user: User,
    *,
    department_id: int,
    email: str | None = None,
) -> Employee:
    employee = Employee(
        employee_number="PENDING",
        first_name=user.first_name,
        last_name=user.last_name,
        email=email or user.email,
        phone="+21620111000",
        department_id=department_id,
        position="Staff",
        hire_date=date(2024, 1, 1),
        employment_status=EmploymentStatus.ACTIVE,
        user_id=user.id,
    )
    db_session.add(employee)
    db_session.flush()
    employee.employee_number = f"EMP-{employee.id:06d}"
    db_session.commit()
    db_session.refresh(employee)
    return employee


def _department_id(db_session) -> int:
    from app.modules.employees.models import Department, DepartmentStatus

    existing = db_session.query(Department).first()
    if existing is not None:
        return existing.id
    department = Department(name="AI Context Dept", status=DepartmentStatus.ACTIVE)
    db_session.add(department)
    db_session.commit()
    db_session.refresh(department)
    return department.id


def test_context_for_admin(db_session):
    admin = _reload_user(db_session, db_session.query(User).filter(User.email == "admin@test.com").one().id)
    ctx = build_ai_execution_context(admin, employees=EmployeeRepository(db_session))
    assert ctx.user_id == admin.id
    assert ctx.has_role("admin")
    assert "users:write" in ctx.permission_names
    assert ctx.employee_id is None
    assert ctx.candidate_id is None


def test_context_for_hr_with_employee_link(db_session):
    user = create_user_with_role(
        db_session,
        email="ai.ctx.hr@test.com",
        password="hrpass123",
        role_name="hr",
        first_name="Amina",
        last_name="HR",
    )
    employee = _link_employee(db_session, user, department_id=_department_id(db_session))
    loaded = _reload_user(db_session, user.id)
    ctx = build_ai_execution_context(loaded, employees=EmployeeRepository(db_session))
    assert ctx.has_role("hr")
    assert ctx.has_any_role("hr", "admin")
    assert "employees:write" in ctx.permission_names
    assert ctx.employee_id == employee.id
    assert ctx.candidate_id is None


def test_context_for_manager(db_session):
    user = create_user_with_role(
        db_session,
        email="ai.ctx.mgr@test.com",
        password="mgrpass123",
        role_name="manager",
    )
    loaded = _reload_user(db_session, user.id)
    ctx = build_ai_execution_context(loaded, employees=EmployeeRepository(db_session))
    assert ctx.role_names == frozenset({"manager"})
    assert ctx.has_role("manager")
    assert "leaves:read" in ctx.permission_names
    assert "recruitment:write" not in ctx.permission_names


def test_context_for_employee(db_session):
    user = create_user_with_role(
        db_session,
        email="ai.ctx.emp@test.com",
        password="emppass123",
        role_name="employee",
    )
    employee = _link_employee(db_session, user, department_id=_department_id(db_session))
    loaded = _reload_user(db_session, user.id)
    ctx = build_ai_execution_context(loaded, employees=EmployeeRepository(db_session))
    assert ctx.has_role("employee")
    assert ctx.employee_id == employee.id
    assert ctx.candidate_id is None


def test_context_for_candidate(db_session):
    user = create_candidate_user(
        db_session,
        email="ai.ctx.cand@test.com",
        password="candpass123",
    )
    loaded = _reload_user(db_session, user.id)
    assert loaded.candidate_profile is not None
    ctx = build_ai_execution_context(loaded, employees=EmployeeRepository(db_session))
    assert ctx.has_role("candidate")
    assert ctx.candidate_id == loaded.candidate_profile.id
    assert ctx.employee_id is None


def test_builder_rejects_identity_override_parameters():
    signature = inspect.signature(build_ai_execution_context)
    assert "employee_id" not in signature.parameters
    assert "candidate_id" not in signature.parameters
    assert "role" not in signature.parameters
    assert "roles" not in signature.parameters
    assert "user_id" not in signature.parameters


def test_claimed_employee_id_cannot_override_authenticated_link(db_session):
    user = create_user_with_role(
        db_session,
        email="ai.ctx.spoof@test.com",
        password="emppass123",
        role_name="employee",
    )
    real = _link_employee(db_session, user, department_id=_department_id(db_session))
    loaded = _reload_user(db_session, user.id)
    # Spoofed claim from an LLM/user message must not be accepted by the builder.
    claimed_employee_id = real.id + 999
    ctx = build_ai_execution_context(loaded, employees=EmployeeRepository(db_session))
    assert ctx.employee_id == real.id
    assert ctx.employee_id != claimed_employee_id
    assert ctx.user_id == loaded.id


def test_unauthenticated_ai_context_dependency_returns_401(client, db_session):
    app = FastAPI()

    @app.get("/__test__/ai-context")
    def _probe(ctx: AIExecutionContext = Depends(get_ai_execution_context)):
        return {"user_id": ctx.user_id}

    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as probe:
        denied = probe.get("/__test__/ai-context")
        assert denied.status_code == 401

        allowed = probe.get(
            "/__test__/ai-context",
            headers=auth_header(client),
        )
        assert allowed.status_code == 200
        admin = db_session.query(User).filter(User.email == "admin@test.com").one()
        assert allowed.json()["user_id"] == admin.id
    app.dependency_overrides.clear()
