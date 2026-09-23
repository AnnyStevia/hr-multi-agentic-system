import pytest

from app.modules.employees.models import Employee
from app.tests.helpers import auth_header, create_department, create_user_with_role, hr_payload, login


def _hr_payload(client, **overrides) -> dict:
    department = create_department(client, name="Human Resources")
    return hr_payload(department["id"], **overrides)


def test_admin_can_create_hr(client, db_session):
    payload = _hr_payload(client)
    response = client.post(
        "/api/v1/users/hr",
        json=payload,
        headers=auth_header(client),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == payload["email"]
    assert data["first_name"] == "Amina"
    assert data["last_name"] == "Benali"
    assert data["full_name"] == "Amina Benali"
    assert data["is_active"] is True
    assert [role["name"] for role in data["roles"]] == ["hr"]
    assert "hashed_password" not in data
    assert "password" not in data
    assert payload["password"] not in str(data)

    employee = db_session.query(Employee).filter(Employee.email == payload["email"]).one()
    assert employee.user_id == data["id"]
    assert employee.employee_number.startswith("EMP-")
    assert employee.position == "HR Officer"
    assert employee.phone == "+216 20 111 222"


def test_created_hr_appears_in_employee_list(client):
    payload = _hr_payload(client)
    created = client.post("/api/v1/users/hr", json=payload, headers=auth_header(client))
    assert created.status_code == 201

    listing = client.get("/api/v1/employees", headers=auth_header(client))
    assert listing.status_code == 200
    emails = [item["email"] for item in listing.json()["items"]]
    assert payload["email"] in emails


def test_created_hr_can_login(client):
    payload = _hr_payload(client)
    create_response = client.post(
        "/api/v1/users/hr",
        json=payload,
        headers=auth_header(client),
    )
    assert create_response.status_code == 201

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == payload["email"]
    assert any(role["name"] == "hr" for role in me.json()["roles"])


def test_password_is_hashed(client, db_session):
    from app.core.security import verify_password
    from app.modules.identity.models import User

    payload = _hr_payload(client)
    response = client.post(
        "/api/v1/users/hr",
        json=payload,
        headers=auth_header(client),
    )
    assert response.status_code == 201

    user = db_session.query(User).filter(User.email == payload["email"]).one()
    assert user.hashed_password != payload["password"]
    assert verify_password(payload["password"], user.hashed_password)
    assert "hashed_password" not in response.json()


def test_hr_cannot_create_hr(client, db_session):
    create_user_with_role(
        db_session,
        email="existing.hr@test.com",
        password="hrpass123",
        role_name="hr",
    )
    response = client.post(
        "/api/v1/users/hr",
        json=_hr_payload(client),
        headers=auth_header(client, "existing.hr@test.com", "hrpass123"),
    )
    assert response.status_code == 403


@pytest.mark.parametrize("role_name", ["manager", "employee"])
def test_non_admin_roles_cannot_create_hr(client, db_session, role_name):
    email = f"{role_name}@test.com"
    create_user_with_role(
        db_session,
        email=email,
        password="rolepass123",
        role_name=role_name,
    )
    response = client.post(
        "/api/v1/users/hr",
        json=_hr_payload(client),
        headers=auth_header(client, email, "rolepass123"),
    )
    assert response.status_code == 403


def test_unauthorized_user_cannot_create_hr(client):
    department = create_department(client)
    response = client.post("/api/v1/users/hr", json=hr_payload(department["id"]))
    assert response.status_code == 401


def test_duplicate_email_is_rejected(client):
    headers = auth_header(client)
    payload = _hr_payload(client)
    first = client.post("/api/v1/users/hr", json=payload, headers=headers)
    assert first.status_code == 201

    second = client.post("/api/v1/users/hr", json=payload, headers=headers)
    assert second.status_code == 409
    assert "email" in second.json()["detail"].lower()


def test_invalid_department_is_rejected(client):
    response = client.post(
        "/api/v1/users/hr",
        json=hr_payload(9999),
        headers=auth_header(client),
    )
    assert response.status_code == 400


def test_inactive_department_is_rejected(client):
    department = create_department(client, name="Closed HR")
    client.patch(f"/api/v1/departments/{department['id']}/deactivate", headers=auth_header(client))
    response = client.post(
        "/api/v1/users/hr",
        json=hr_payload(department["id"]),
        headers=auth_header(client),
    )
    assert response.status_code == 400


def test_invalid_email_is_rejected(client):
    response = client.post(
        "/api/v1/users/hr",
        json={**_hr_payload(client), "email": "not-an-email"},
        headers=auth_header(client),
    )
    assert response.status_code == 422


def test_invalid_password_is_rejected(client):
    response = client.post(
        "/api/v1/users/hr",
        json={**_hr_payload(client), "password": "short"},
        headers=auth_header(client),
    )
    assert response.status_code == 422


def test_missing_required_fields_are_rejected(client):
    response = client.post(
        "/api/v1/users/hr",
        json={"email": "incomplete@test.com"},
        headers=auth_header(client),
    )
    assert response.status_code == 422


def test_client_cannot_assign_arbitrary_role(client):
    response = client.post(
        "/api/v1/users/hr",
        json={**_hr_payload(client), "role": "admin"},
        headers=auth_header(client),
    )
    assert response.status_code == 422


def test_inactive_admin_cannot_create_hr(client, db_session):
    from app.modules.identity.models import User

    create_user_with_role(
        db_session,
        email="inactive.admin@test.com",
        password="adminpass123",
        role_name="admin",
        is_active=True,
    )
    token = login(client, "inactive.admin@test.com", "adminpass123")

    inactive = db_session.query(User).filter(User.email == "inactive.admin@test.com").one()
    inactive.is_active = False
    db_session.commit()

    response = client.post(
        "/api/v1/users/hr",
        json=_hr_payload(client),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


def test_admin_create_hr_rejects_inactive_manager_allows_active(client, db_session):
    headers = auth_header(client)
    department = create_department(client, name="HR Mgr Check")

    active = client.post(
        "/api/v1/employees",
        json={
            "first_name": "Dir",
            "last_name": "Active",
            "email": "dir.active.hr@test.com",
            "phone": "+216 20 600 100",
            "department_id": department["id"],
            "position": "Director",
            "hire_date": "2020-01-01",
        },
        headers=headers,
    ).json()
    inactive = client.post(
        "/api/v1/employees",
        json={
            "first_name": "Dir",
            "last_name": "Inactive",
            "email": "dir.inactive.hr@test.com",
            "phone": "+216 20 600 101",
            "department_id": department["id"],
            "position": "Former Director",
            "hire_date": "2019-01-01",
        },
        headers=headers,
    ).json()
    assert (
        client.patch(
            f"/api/v1/employees/{inactive['id']}/deactivate",
            headers=headers,
        ).status_code
        == 200
    )

    blocked = client.post(
        "/api/v1/users/hr",
        json=hr_payload(
            department["id"],
            email="hr.blocked.mgr@test.com",
            manager_id=inactive["id"],
        ),
        headers=headers,
    )
    assert blocked.status_code == 400
    assert "active" in blocked.json()["detail"].lower()

    allowed = client.post(
        "/api/v1/users/hr",
        json=hr_payload(
            department["id"],
            email="hr.allowed.mgr@test.com",
            manager_id=active["id"],
        ),
        headers=headers,
    )
    assert allowed.status_code == 201
    employee = (
        db_session.query(Employee).filter(Employee.email == "hr.allowed.mgr@test.com").one()
    )
    assert employee.manager_id == active["id"]
