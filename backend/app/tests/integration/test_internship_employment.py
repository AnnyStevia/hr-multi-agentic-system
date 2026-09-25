from datetime import date, timedelta

from app.modules.employees.models import Employee
from app.modules.employees.service import add_months
from app.modules.identity.models import Role, UserRole
from app.modules.recruitment.models import EmploymentType, Job
from app.tests.helpers import auth_header, create_department
from app.tests.integration.test_interview_outcomes import _complete, _schedule_interview
from app.tests.integration.test_jobs import _payload


def test_internship_job_requires_duration_months(client):
    headers = auth_header(client)
    missing = client.post(
        "/api/v1/jobs",
        json=_payload(client, employment_type="internship"),
        headers=headers,
    )
    assert missing.status_code == 422, missing.text

    created = client.post(
        "/api/v1/jobs",
        json=_payload(
            client,
            employment_type="internship",
            internship_duration_months=6,
        ),
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["employment_type"] == "internship"
    assert created.json()["internship_duration_months"] == 6

    non_intern = client.post(
        "/api/v1/jobs",
        json=_payload(
            client,
            title="Staff Engineer",
            employment_type="full_time",
            internship_duration_months=3,
        ),
        headers=headers,
    )
    assert non_intern.status_code == 422, non_intern.text


def test_hire_from_internship_job_copies_type_and_convert(client, db_session):
    _application, job, _cand, headers, interview = _schedule_interview(
        client, db_session, email="intern.hire@test.com"
    )
    job_row = db_session.query(Job).filter(Job.id == job["id"]).one()
    job_row.employment_type = EmploymentType.INTERNSHIP
    job_row.internship_duration_months = 6
    db_session.commit()

    completed = _complete(client, headers, interview["id"])
    hired = client.post(
        f"/api/v1/interviews/{completed['id']}/outcome",
        json={"outcome": "hired"},
        headers=headers,
    )
    assert hired.status_code == 200, hired.text
    intern_id = hired.json()["hired_employee_id"]
    intern = db_session.query(Employee).filter(Employee.id == intern_id).one()
    assert intern.employment_type == EmploymentType.INTERNSHIP
    assert intern.employment_end_date == add_months(intern.hire_date, 6)
    assert intern.user_id is not None
    hire_date_before = intern.hire_date
    user_id_before = intern.user_id

    roles = (
        db_session.query(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(UserRole.user_id == intern.user_id)
        .all()
    )
    assert "employee" in {name for (name,) in roles}

    converted = client.post(
        f"/api/v1/employees/{intern_id}/convert-to-employee",
        headers=headers,
    )
    assert converted.status_code == 200, converted.text
    assert converted.json()["employment_type"] == "full_time"
    assert converted.json()["employment_end_date"] is None
    assert converted.json()["hire_date"] == hire_date_before.isoformat()
    assert converted.json()["id"] == intern_id
    assert converted.json()["user_id"] == user_id_before

    again = client.post(
        f"/api/v1/employees/{intern_id}/convert-to-employee",
        headers=headers,
    )
    assert again.status_code == 200, again.text
    assert again.json()["employment_type"] == "full_time"
    assert again.json()["id"] == intern_id


def test_manual_create_intern_employee(client):
    headers = auth_header(client)
    department = create_department(client, name="Internships")
    hire_date = date.today()
    end_date = hire_date + timedelta(days=180)
    created = client.post(
        "/api/v1/employees",
        json={
            "first_name": "Intern",
            "last_name": "Manual",
            "email": "intern.manual@test.com",
            "phone": "+216 20 999 888",
            "department_id": department["id"],
            "position": "Product Intern",
            "hire_date": hire_date.isoformat(),
            "employment_type": "internship",
            "employment_end_date": end_date.isoformat(),
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["employment_type"] == "internship"
    assert created.json()["employment_end_date"] == end_date.isoformat()

    ft = client.post(
        "/api/v1/employees",
        json={
            "first_name": "Full",
            "last_name": "Timer",
            "email": "full.timer@test.com",
            "phone": "+216 20 999 777",
            "department_id": department["id"],
            "position": "Engineer",
            "hire_date": hire_date.isoformat(),
            "employment_type": "full_time",
        },
        headers=headers,
    )
    assert ft.status_code == 201, ft.text
    idempotent = client.post(
        f"/api/v1/employees/{ft.json()['id']}/convert-to-employee",
        headers=headers,
    )
    assert idempotent.status_code == 200, idempotent.text
    assert idempotent.json()["employment_type"] == "full_time"
