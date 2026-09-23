from datetime import UTC, date, datetime, timedelta

from app.modules.employees.models import EmploymentStatus
from app.modules.identity.models import Candidate
from app.modules.leave.models import LeaveRequest, LeaveRequestStatus
from app.modules.onboarding.models import (
    Onboarding,
    OnboardingStatus,
    OnboardingTask,
    OnboardingTaskStatus,
    OnboardingTaskType,
)
from app.modules.recruitment.models import Application, ApplicationStatus
from app.tests.helpers import (
    auth_header,
    create_candidate_user,
    create_department,
    create_user_with_role,
    job_payload,
)
from app.tests.integration.test_organization import _create_linked_employee


def test_hr_and_admin_can_access_dashboard_employee_cannot(client, db_session):
    admin = auth_header(client)
    empty = client.get("/api/v1/hr/dashboard", headers=admin)
    assert empty.status_code == 200, empty.text
    body = empty.json()
    assert body["kpis"]["total_employees"] == 0
    assert body["kpis"]["active_employees"] == 0
    assert body["kpis"]["on_leave"] == 0
    assert body["kpis"]["pending_leave"] == 0
    assert body["kpis"]["onboarding"] == 0
    assert body["kpis"]["open_jobs"] == 0
    assert body["kpis"]["pending_applications"] == 0
    assert body["workforce"]["by_department"] == []
    assert body["activity"]["recent_hires"] == []
    assert body["attention"]["pending_leave"] == []
    assert body["leave_overview"] == {"approved": 0, "pending": 0, "rejected": 0}
    assert body["activity"]["upcoming_deadlines"] == []

    create_user_with_role(
        db_session, email="dash.hr@test.com", password="hrpass123", role_name="hr"
    )
    hr = auth_header(client, "dash.hr@test.com", "hrpass123")
    assert client.get("/api/v1/hr/dashboard", headers=hr).status_code == 200

    create_user_with_role(
        db_session, email="dash.emp@test.com", password="emppass123", role_name="employee"
    )
    emp = auth_header(client, "dash.emp@test.com", "emppass123")
    assert client.get("/api/v1/hr/dashboard", headers=emp).status_code == 403

    create_user_with_role(
        db_session, email="dash.mgr@test.com", password="mgrpass123", role_name="manager"
    )
    mgr = auth_header(client, "dash.mgr@test.com", "mgrpass123")
    assert client.get("/api/v1/hr/dashboard", headers=mgr).status_code == 403


def test_dashboard_kpis_workforce_and_activity(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="DashDept")
    today = date.today()

    _u1, active = _create_linked_employee(
        db_session,
        email="dash.active@test.com",
        password="pass12345",
        department_id=dept["id"],
        first_name="Active",
        last_name="One",
        position="Engineer",
    )
    active.hire_date = today - timedelta(days=2)
    db_session.commit()

    _u2, inactive = _create_linked_employee(
        db_session,
        email="dash.inactive@test.com",
        password="pass12345",
        department_id=dept["id"],
        first_name="Inactive",
        last_name="Two",
        position="Analyst",
    )
    inactive.employment_status = EmploymentStatus.INACTIVE
    db_session.commit()

    # Leave type + policy + pending + approved covering today
    leave_type = client.post(
        "/api/v1/leave/types",
        json={"name": "Dash Annual", "is_paid": True},
        headers=headers,
    )
    assert leave_type.status_code == 201, leave_type.text
    policy = client.post(
        "/api/v1/leave/policies",
        json={
            "leave_type_id": leave_type.json()["id"],
            "year": today.year,
            "days_allowed": 30,
        },
        headers=headers,
    )
    assert policy.status_code == 201, policy.text

    covering = LeaveRequest(
        employee_id=active.id,
        leave_type_id=leave_type.json()["id"],
        start_date=today - timedelta(days=1),
        end_date=today + timedelta(days=3),
        requested_days=5,
        status=LeaveRequestStatus.APPROVED,
    )
    pending = LeaveRequest(
        employee_id=active.id,
        leave_type_id=leave_type.json()["id"],
        start_date=today + timedelta(days=20),
        end_date=today + timedelta(days=21),
        requested_days=2,
        status=LeaveRequestStatus.PENDING,
    )
    db_session.add_all([covering, pending])
    db_session.commit()

    onboarding = Onboarding(
        employee_id=active.id,
        status=OnboardingStatus.IN_PROGRESS,
        started_at=datetime.now(UTC),
    )
    db_session.add(onboarding)
    db_session.commit()

    deadline_task = OnboardingTask(
        onboarding_id=onboarding.id,
        title="Submit ID copy",
        task_type=OnboardingTaskType.DOCUMENT,
        status=OnboardingTaskStatus.PENDING,
        due_date=today + timedelta(days=5),
    )
    db_session.add(deadline_task)
    db_session.commit()

    job = client.post(
        "/api/v1/jobs",
        json=job_payload(department_id=dept["id"], title="Dash Role"),
        headers=headers,
    )
    assert job.status_code == 201, job.text
    published = client.post(f"/api/v1/jobs/{job.json()['id']}/publish", headers=headers)
    assert published.status_code == 200, published.text

    candidate = create_candidate_user(
        db_session, email="dash.cand@test.com", password="candpass123"
    )
    cand_row = db_session.query(Candidate).filter(Candidate.user_id == candidate.id).one()
    application = Application(
        job_id=job.json()["id"],
        candidate_id=cand_row.id,
        status=ApplicationStatus.SUBMITTED,
        submitted_at=datetime.now(UTC),
    )
    db_session.add(application)
    db_session.commit()

    response = client.get("/api/v1/hr/dashboard", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    kpis = data["kpis"]

    assert kpis["total_employees"] >= 2
    assert kpis["active_employees"] >= 1
    assert kpis["on_leave"] >= 1
    assert kpis["pending_leave"] >= 1
    assert kpis["onboarding"] >= 1
    assert kpis["open_jobs"] >= 1
    assert kpis["pending_applications"] >= 1

    dept_labels = {row["label"] for row in data["workforce"]["by_department"]}
    assert "DashDept" in dept_labels
    status_labels = {row["label"] for row in data["workforce"]["by_employment_status"]}
    assert "active" in status_labels
    assert "inactive" in status_labels

    assert any(item["employee_id"] == active.id for item in data["activity"]["on_leave"])
    assert any(item["employee_id"] == active.id for item in data["activity"]["returning_soon"])
    assert any(item["employee_id"] == active.id for item in data["activity"]["recent_hires"])
    assert any(
        item["request_id"] == pending.id for item in data["attention"]["pending_leave"]
    )
    assert any(
        item["application_id"] == application.id
        for item in data["attention"]["pending_applications"]
    )
    assert any(
        item["onboarding_id"] == onboarding.id
        for item in data["attention"]["incomplete_onboarding"]
    )

    overview = data["leave_overview"]
    assert overview["approved"] >= 1
    assert overview["pending"] >= 1
    assert overview["rejected"] >= 0
    assert any(
        item["onboarding_id"] == onboarding.id
        and item["task_title"] == "Submit ID copy"
        for item in data["activity"]["upcoming_deadlines"]
    )
