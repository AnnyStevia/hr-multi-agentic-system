from app.tests.helpers import auth_header, create_candidate_user, create_department, create_user_with_role


def test_hr_can_create_and_list_departments(client, db_session):
    create_user_with_role(db_session, email="hr.dept@test.com", password="hrpass123", role_name="hr")
    headers = auth_header(client, "hr.dept@test.com", "hrpass123")
    created = client.post("/api/v1/departments", json={"name": "People"}, headers=headers)
    assert created.status_code == 201
    assert created.json()["status"] == "active"
    listing = client.get("/api/v1/departments?status=active", headers=headers)
    assert listing.status_code == 200
    assert any(item["name"] == "People" for item in listing.json())


def test_admin_can_create_department(client):
    created = create_department(client, name="Finance")
    assert created["name"] == "Finance"


def test_candidate_cannot_create_department(client, db_session):
    create_candidate_user(db_session, email="cand.dept@test.com", password="candidate123")
    response = client.post(
        "/api/v1/departments",
        json={"name": "Secret"},
        headers=auth_header(client, "cand.dept@test.com", "candidate123"),
    )
    assert response.status_code == 403


def test_employee_cannot_list_departments(client, db_session):
    create_user_with_role(db_session, email="emp.dept@test.com", password="emppass123", role_name="employee")
    response = client.get(
        "/api/v1/departments",
        headers=auth_header(client, "emp.dept@test.com", "emppass123"),
    )
    assert response.status_code == 403


def test_unauthenticated_cannot_list_departments(client):
    assert client.get("/api/v1/departments").status_code == 401


def test_duplicate_department_name_rejected(client):
    create_department(client, name="Legal")
    response = client.post("/api/v1/departments", json={"name": "Legal"}, headers=auth_header(client))
    assert response.status_code == 409


def test_deactivate_department_keeps_record(client):
    department = create_department(client, name="Ops")
    response = client.patch(
        f"/api/v1/departments/{department['id']}/deactivate",
        headers=auth_header(client),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "inactive"
    active = client.get("/api/v1/departments?status=active", headers=auth_header(client))
    assert all(item["id"] != department["id"] for item in active.json())
    detail = client.get(f"/api/v1/departments/{department['id']}", headers=auth_header(client))
    assert detail.status_code == 200
    assert detail.json()["status"] == "inactive"
