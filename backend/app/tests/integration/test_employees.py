from app.modules.employees.models import Employee, EmploymentStatus
from app.tests.helpers import auth_header, create_candidate_user, create_department, create_user_with_role


def _employee_payload(department_id: int, **overrides) -> dict:
    payload = {
        "first_name": "Amine",
        "last_name": "Ben Ali",
        "email": "amine.hr@test.com",
        "phone": "+216 20 111 222",
        "department_id": department_id,
        "position": "HR Officer",
        "hire_date": "2024-01-15",
    }
    payload.update(overrides)
    return payload


def _hr_headers(client, db_session):
    create_user_with_role(db_session, email="hr.emp@test.com", password="hrpass123", role_name="hr")
    return auth_header(client, "hr.emp@test.com", "hrpass123")


def test_hr_can_create_employee(client, db_session):
    department = create_department(client)
    response = client.post(
        "/api/v1/employees",
        json=_employee_payload(department["id"]),
        headers=_hr_headers(client, db_session),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["employee_number"] == f"EMP-{body['id']:06d}"
    assert body["employment_status"] == "active"
    assert body["department"] == "Engineering"
    assert body["user_id"] is None


def test_admin_can_create_employee(client):
    department = create_department(client)
    response = client.post(
        "/api/v1/employees",
        json=_employee_payload(department["id"], email="admin.created@test.com"),
        headers=auth_header(client),
    )
    assert response.status_code == 201
    assert response.json()["employee_number"].startswith("EMP-")


def test_unauthorized_cannot_create_employee(client):
    response = client.post("/api/v1/employees", json=_employee_payload(1))
    assert response.status_code == 401


def test_candidate_cannot_create_employee(client, db_session):
    create_candidate_user(db_session, email="cand.emp@test.com", password="candidate123")
    department = create_department(client)
    response = client.post(
        "/api/v1/employees",
        json=_employee_payload(department["id"]),
        headers=auth_header(client, "cand.emp@test.com", "candidate123"),
    )
    assert response.status_code == 403


def test_role_employee_cannot_create_employee(client, db_session):
    create_user_with_role(db_session, email="staff@test.com", password="emppass123", role_name="employee")
    department = create_department(client)
    response = client.post(
        "/api/v1/employees",
        json=_employee_payload(department["id"]),
        headers=auth_header(client, "staff@test.com", "emppass123"),
    )
    assert response.status_code == 403


def test_employee_numbers_are_unique(client):
    department = create_department(client)
    first = client.post(
        "/api/v1/employees",
        json=_employee_payload(department["id"], email="one@test.com"),
        headers=auth_header(client),
    )
    second = client.post(
        "/api/v1/employees",
        json=_employee_payload(department["id"], email="two@test.com"),
        headers=auth_header(client),
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["employee_number"] != second.json()["employee_number"]


def test_invalid_department_rejected(client):
    response = client.post(
        "/api/v1/employees",
        json=_employee_payload(9999),
        headers=auth_header(client),
    )
    assert response.status_code == 400


def test_inactive_department_rejected(client):
    department = create_department(client, name="ClosedDept")
    client.patch(f"/api/v1/departments/{department['id']}/deactivate", headers=auth_header(client))
    response = client.post(
        "/api/v1/employees",
        json=_employee_payload(department["id"]),
        headers=auth_header(client),
    )
    assert response.status_code == 400


def test_hr_and_admin_can_list_and_get_employee(client, db_session):
    department = create_department(client)
    created = client.post(
        "/api/v1/employees",
        json=_employee_payload(department["id"]),
        headers=auth_header(client),
    ).json()
    hr = _hr_headers(client, db_session)
    listing = client.get("/api/v1/employees", headers=hr)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    detail = client.get(f"/api/v1/employees/{created['id']}", headers=auth_header(client))
    assert detail.status_code == 200
    assert detail.json()["email"] == "amine.hr@test.com"


def test_unauthorized_cannot_get_employee(client):
    department = create_department(client)
    created = client.post(
        "/api/v1/employees",
        json=_employee_payload(department["id"]),
        headers=auth_header(client),
    ).json()
    assert client.get(f"/api/v1/employees/{created['id']}").status_code == 401
    assert client.get("/api/v1/employees").status_code == 401


def test_hr_and_admin_can_update_employee(client, db_session):
    department = create_department(client)
    other = create_department(client, name="Finance")
    created = client.post(
        "/api/v1/employees",
        json=_employee_payload(department["id"]),
        headers=auth_header(client),
    ).json()
    updated = client.patch(
        f"/api/v1/employees/{created['id']}",
        json={"position": "Senior HR Officer", "department_id": other["id"]},
        headers=_hr_headers(client, db_session),
    )
    assert updated.status_code == 200
    assert updated.json()["position"] == "Senior HR Officer"
    assert updated.json()["department"] == "Finance"


def test_unauthorized_cannot_update_employee(client):
    department = create_department(client)
    created = client.post(
        "/api/v1/employees",
        json=_employee_payload(department["id"]),
        headers=auth_header(client),
    ).json()
    response = client.patch(
        f"/api/v1/employees/{created['id']}",
        json={"position": "Hacker"},
    )
    assert response.status_code == 401


def test_hr_and_admin_can_deactivate_employee(client, db_session):
    department = create_department(client)
    created = client.post(
        "/api/v1/employees",
        json=_employee_payload(department["id"]),
        headers=auth_header(client),
    ).json()
    deactivated = client.patch(
        f"/api/v1/employees/{created['id']}/deactivate",
        headers=_hr_headers(client, db_session),
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["employment_status"] == "inactive"
    employee = db_session.query(Employee).filter(Employee.id == created["id"]).one()
    assert employee.employment_status == EmploymentStatus.INACTIVE
    listing = client.get("/api/v1/employees", headers=auth_header(client))
    assert listing.json()["total"] == 0
    inactive = client.get("/api/v1/employees?status=inactive", headers=auth_header(client))
    assert inactive.json()["total"] == 1
    detail = client.get(f"/api/v1/employees/{created['id']}", headers=auth_header(client))
    assert detail.status_code == 200


def test_filters_and_search(client):
    engineering = create_department(client, name="Engineering")
    finance = create_department(client, name="Finance")
    client.post(
        "/api/v1/employees",
        json=_employee_payload(engineering["id"], first_name="Sami", email="sami@test.com"),
        headers=auth_header(client),
    )
    other = client.post(
        "/api/v1/employees",
        json=_employee_payload(finance["id"], first_name="Nour", last_name="Khelifi", email="nour@test.com"),
        headers=auth_header(client),
    ).json()
    client.patch(f"/api/v1/employees/{other['id']}/deactivate", headers=auth_header(client))

    active = client.get("/api/v1/employees", headers=auth_header(client))
    assert active.json()["total"] == 1
    assert active.json()["items"][0]["first_name"] == "Sami"

    by_dept = client.get(
        f"/api/v1/employees?status=all&department_id={finance['id']}",
        headers=auth_header(client),
    )
    assert by_dept.json()["total"] == 1
    assert by_dept.json()["items"][0]["first_name"] == "Nour"

    search = client.get("/api/v1/employees?status=all&q=EMP-", headers=auth_header(client))
    assert search.json()["total"] == 2
    named = client.get("/api/v1/employees?status=all&q=Sami", headers=auth_header(client))
    assert named.json()["total"] == 1
