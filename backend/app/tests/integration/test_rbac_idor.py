"""RBAC / IDOR regression coverage for Core HR stabilization."""

from datetime import UTC, date, datetime, timedelta

from app.modules.employees.models import Employee, EmploymentStatus
from app.modules.identity.models import Role, User, UserRole
from app.modules.leave.models import LeaveRequest, LeaveRequestStatus
from app.modules.notifications.models import Notification, NotificationType
from app.modules.onboarding.models import (
    Onboarding,
    OnboardingStatus,
    OnboardingTask,
    OnboardingTaskStatus,
    OnboardingTaskType,
)
from app.core.security import get_password_hash
from app.tests.helpers import (
    auth_header,
    create_candidate_user,
    create_department,
    create_user_with_role,
    job_payload,
)


def _linked_employee(
    db_session,
    *,
    email: str,
    password: str,
    department_id: int,
    role_name: str = "employee",
    first_name: str = "Sam",
    last_name: str = "Staff",
    manager_id: int | None = None,
) -> tuple[User, Employee]:
    role = db_session.query(Role).filter(Role.name == role_name).one()
    user = User(
        email=email,
        hashed_password=get_password_hash(password),
        first_name=first_name,
        last_name=last_name,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=role.id))
    employee = Employee(
        employee_number="PENDING",
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone="+21620111222",
        department_id=department_id,
        position="Engineer",
        manager_id=manager_id,
        hire_date=date(2024, 1, 1),
        employment_status=EmploymentStatus.ACTIVE,
        user_id=user.id,
    )
    db_session.add(employee)
    db_session.flush()
    employee.employee_number = f"EMP-{employee.id:06d}"
    db_session.commit()
    db_session.refresh(employee)
    return user, employee


def test_manager_cannot_access_hr_recruitment_or_onboarding(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="RbacDept")
    create_user_with_role(
        db_session, email="mgr.rbac@test.com", password="mgrpass123", role_name="manager"
    )
    mgr = auth_header(client, "mgr.rbac@test.com", "mgrpass123")

    job = client.post(
        "/api/v1/jobs",
        json=job_payload(dept["id"], title="Rbac Role"),
        headers=headers,
    )
    assert job.status_code == 201, job.text
    job_id = job.json()["id"]

    assert client.get("/api/v1/jobs", headers=mgr).status_code == 403
    assert client.get(f"/api/v1/jobs/{job_id}", headers=mgr).status_code == 403
    assert client.get("/api/v1/onboarding", headers=mgr).status_code == 403
    assert client.get("/api/v1/onboarding/task-templates", headers=mgr).status_code == 403


def test_employee_and_candidate_blocked_from_hr_recruitment(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="RbacDept2")
    create_user_with_role(
        db_session, email="emp.rbac@test.com", password="emppass123", role_name="employee"
    )
    create_candidate_user(db_session, email="cand.rbac@test.com", password="candpass123")
    emp = auth_header(client, "emp.rbac@test.com", "emppass123")
    cand = auth_header(client, "cand.rbac@test.com", "candpass123")

    job = client.post(
        "/api/v1/jobs",
        json=job_payload(dept["id"], title="Secret Role"),
        headers=headers,
    )
    assert job.status_code == 201, job.text

    for auth in (emp, cand):
        assert client.get("/api/v1/jobs", headers=auth).status_code == 403
        assert client.get("/api/v1/onboarding", headers=auth).status_code == 403


def test_employee_cannot_read_or_approve_other_leave_request(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="LeaveIdor")
    _u_a, emp_a = _linked_employee(
        db_session, email="leave.a@test.com", password="pass12345", department_id=dept["id"]
    )
    _u_b, emp_b = _linked_employee(
        db_session,
        email="leave.b@test.com",
        password="pass12345",
        department_id=dept["id"],
        first_name="Other",
        last_name="Person",
    )

    leave_type = client.post(
        "/api/v1/leave/types",
        json={"name": "Idor Annual", "is_paid": True},
        headers=headers,
    )
    assert leave_type.status_code == 201, leave_type.text
    policy = client.post(
        "/api/v1/leave/policies",
        json={
            "leave_type_id": leave_type.json()["id"],
            "year": date.today().year,
            "days_allowed": 20,
        },
        headers=headers,
    )
    assert policy.status_code == 201, policy.text

    today = date.today()
    pending = LeaveRequest(
        employee_id=emp_a.id,
        leave_type_id=leave_type.json()["id"],
        start_date=today + timedelta(days=10),
        end_date=today + timedelta(days=11),
        requested_days=2,
        status=LeaveRequestStatus.PENDING,
    )
    db_session.add(pending)
    db_session.commit()

    b_headers = auth_header(client, "leave.b@test.com", "pass12345")
    get_other = client.get(f"/api/v1/leave/requests/{pending.id}", headers=b_headers)
    assert get_other.status_code in (403, 404)

    approve = client.patch(
        f"/api/v1/leave/requests/{pending.id}/approve", headers=b_headers
    )
    assert approve.status_code == 403


def test_notification_mark_read_is_owner_scoped(client, db_session):
    dept = create_department(client, name="NotifIdor")
    _ua, _ea = _linked_employee(
        db_session, email="notif.a@test.com", password="pass12345", department_id=dept["id"]
    )
    _ub, _eb = _linked_employee(
        db_session,
        email="notif.b@test.com",
        password="pass12345",
        department_id=dept["id"],
        first_name="Bee",
        last_name="User",
    )
    note = Notification(
        recipient_user_id=_ua.id,
        type=NotificationType.LEAVE_REQUEST_SUBMITTED,
        title="Private",
        message="Only A",
        is_read=False,
    )
    db_session.add(note)
    db_session.commit()

    b_headers = auth_header(client, "notif.b@test.com", "pass12345")
    response = client.patch(f"/api/v1/notifications/{note.id}/read", headers=b_headers)
    assert response.status_code == 404


def test_cannot_mutate_tasks_after_onboarding_completed(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="OnbDone")
    _user, emp = _linked_employee(
        db_session, email="onb.done@test.com", password="pass12345", department_id=dept["id"]
    )
    onboarding = Onboarding(
        employee_id=emp.id,
        status=OnboardingStatus.COMPLETED,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    db_session.add(onboarding)
    db_session.flush()
    task = OnboardingTask(
        onboarding_id=onboarding.id,
        title="Manual wrap-up",
        task_type=OnboardingTaskType.MANUAL,
        status=OnboardingTaskStatus.COMPLETED,
        is_required=True,
    )
    db_session.add(task)
    db_session.commit()

    patch = client.patch(
        f"/api/v1/onboarding/tasks/{task.id}",
        json={"status": "pending"},
        headers=headers,
    )
    assert patch.status_code == 400, patch.text

    delete = client.delete(f"/api/v1/onboarding/tasks/{task.id}", headers=headers)
    assert delete.status_code == 400, delete.text

    complete = client.patch(
        f"/api/v1/onboarding/tasks/{task.id}/complete", headers=headers
    )
    assert complete.status_code == 400, complete.text


def test_document_me_url_cannot_access_other_employee_document(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="DocIdor")
    _ua, emp_a = _linked_employee(
        db_session, email="doc.a@test.com", password="pass12345", department_id=dept["id"]
    )
    _ub, emp_b = _linked_employee(
        db_session,
        email="doc.b@test.com",
        password="pass12345",
        department_id=dept["id"],
        first_name="Doc",
        last_name="Bee",
    )

    # Create a document row directly for A (skip S3 for IDOR of ownership lookup)
    from app.modules.documents.models import Document, DocumentType

    doc = Document(
        employee_id=emp_a.id,
        document_type=DocumentType.ID_DOCUMENT,
        original_filename="id.pdf",
        content_type="application/pdf",
        size_bytes=10,
        storage_key=f"employees/{emp_a.id}/documents/1/id.pdf",
        uploaded_at=datetime.now(UTC),
    )
    db_session.add(doc)
    db_session.commit()

    b_headers = auth_header(client, "doc.b@test.com", "pass12345")
    response = client.get(f"/api/v1/me/documents/{doc.id}/url", headers=b_headers)
    assert response.status_code == 404

    # HR path still requires matching employee_id
    mismatch = client.get(
        f"/api/v1/employees/{emp_b.id}/documents/{doc.id}/url",
        headers=headers,
    )
    assert mismatch.status_code == 404
