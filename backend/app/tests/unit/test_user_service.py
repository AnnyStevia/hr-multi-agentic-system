from datetime import date

from app.core.security import verify_password
from app.modules.employees.models import Department, DepartmentStatus, Employee, EmploymentStatus
from app.modules.identity.models import Candidate, Role, User
from app.modules.identity.service import SeedService, UserService
from app.shared.exceptions import AppException


def _active_department(db_session, name: str = "Human Resources") -> Department:
    department = Department(name=name, status=DepartmentStatus.ACTIVE)
    db_session.add(department)
    db_session.commit()
    db_session.refresh(department)
    return department


def test_create_hr_assigns_hr_role_and_hashes_password(db_session):
    department = _active_department(db_session)
    service = UserService(db_session)
    manager = Employee(
        employee_number="PENDING",
        first_name="Dir",
        last_name="Ector",
        email="director@test.com",
        phone="+21620111000",
        department_id=department.id,
        position="Director",
        hire_date=date(2020, 1, 1),
        employment_status=EmploymentStatus.ACTIVE,
    )
    db_session.add(manager)
    db_session.flush()
    manager.employee_number = f"EMP-{manager.id:06d}"
    db_session.commit()

    user = service.create_hr_account(
        first_name="Sara",
        last_name="Khelifi",
        email="sara.hr@test.com",
        password="hrpass123",
        phone="+216 20 333 444",
        department_id=department.id,
        position="HR Manager",
        hire_date=date(2024, 3, 1),
        manager_id=manager.id,
    )

    assert user.email == "sara.hr@test.com"
    assert [ur.role.name for ur in user.user_roles] == ["hr"]
    assert user.hashed_password != "hrpass123"
    assert verify_password("hrpass123", user.hashed_password)

    employee = db_session.query(Employee).filter(Employee.user_id == user.id).one()
    assert employee.email == "sara.hr@test.com"
    assert employee.employee_number.startswith("EMP-")
    assert employee.department_id == department.id
    assert employee.manager_id == manager.id
    assert employee.position == "HR Manager"


def test_create_hr_rejects_inactive_manager(db_session):
    department = _active_department(db_session)
    service = UserService(db_session)
    manager = Employee(
        employee_number="PENDING",
        first_name="Former",
        last_name="Boss",
        email="former.boss@test.com",
        phone="+21620111001",
        department_id=department.id,
        position="Director",
        hire_date=date(2020, 1, 1),
        employment_status=EmploymentStatus.INACTIVE,
    )
    db_session.add(manager)
    db_session.flush()
    manager.employee_number = f"EMP-{manager.id:06d}"
    db_session.commit()

    try:
        service.create_hr_account(
            first_name="Sara",
            last_name="Khelifi",
            email="sara.inactive.mgr@test.com",
            password="hrpass123",
            phone="+216 20 333 444",
            department_id=department.id,
            position="HR Manager",
            hire_date=date(2024, 3, 1),
            manager_id=manager.id,
        )
        raise AssertionError("Expected inactive manager to fail")
    except AppException as exc:
        assert exc.status_code == 400
        assert "active" in str(exc).lower()
        assert (
            db_session.query(Employee)
            .filter(Employee.email == "sara.inactive.mgr@test.com")
            .count()
            == 0
        )


def test_create_hr_rejects_nonexistent_manager(db_session):
    department = _active_department(db_session)
    service = UserService(db_session)
    try:
        service.create_hr_account(
            first_name="Sara",
            last_name="Khelifi",
            email="sara.missing.mgr@test.com",
            password="hrpass123",
            phone="+216 20 333 444",
            department_id=department.id,
            position="HR Manager",
            hire_date=date(2024, 3, 1),
            manager_id=999999,
        )
        raise AssertionError("Expected missing manager to fail")
    except AppException as exc:
        assert exc.status_code == 404


def test_create_hr_rejects_duplicate_email(db_session):
    department = _active_department(db_session)
    service = UserService(db_session)
    service.create_hr_account(
        first_name="Sara",
        last_name="Khelifi",
        email="sara.hr@test.com",
        password="hrpass123",
        phone="+216 20 333 444",
        department_id=department.id,
        position="HR Specialist",
        hire_date=date(2024, 3, 1),
    )

    try:
        service.create_hr_account(
            first_name="Other",
            last_name="User",
            email="sara.hr@test.com",
            password="hrpass456",
            phone="+216 20 555 666",
            department_id=department.id,
            position="HR Specialist",
            hire_date=date(2024, 3, 1),
        )
        raise AssertionError("Expected duplicate email to fail")
    except AppException as exc:
        assert exc.status_code == 409
        assert db_session.query(User).filter(User.email == "sara.hr@test.com").count() == 1
        assert db_session.query(Employee).filter(Employee.email == "sara.hr@test.com").count() == 1


def test_register_candidate_assigns_role_profile_and_hashes_password(db_session):
    service = UserService(db_session)
    user = service.register_candidate(
        first_name="Lina",
        last_name="Trabelsi",
        email="lina.candidate@test.com",
        password="candidate123",
    )

    assert [ur.role.name for ur in user.user_roles] == ["candidate"]
    assert db_session.query(Candidate).filter(Candidate.user_id == user.id).one()
    assert verify_password("candidate123", user.hashed_password)


def test_register_candidate_rejects_duplicate_email(db_session):
    service = UserService(db_session)
    service.register_candidate(
        first_name="Lina",
        last_name="Trabelsi",
        email="lina.candidate@test.com",
        password="candidate123",
    )

    try:
        service.register_candidate(
            first_name="Other",
            last_name="User",
            email="lina.candidate@test.com",
            password="candidate456",
        )
        raise AssertionError("Expected duplicate email to fail")
    except AppException as exc:
        assert exc.status_code == 409


def test_seed_adds_missing_candidate_role(db_session):
    SeedService(db_session)._ensure_candidate_role()
    assert db_session.query(Role).filter(Role.name == "candidate").one()
