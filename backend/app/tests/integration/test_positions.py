from app.tests.helpers import auth_header, create_department, create_user_with_role


def test_hr_can_create_and_list_positions(client, db_session):
    create_user_with_role(db_session, email="hr.pos@test.com", password="hrpass123", role_name="hr")
    headers = auth_header(client, "hr.pos@test.com", "hrpass123")
    department = create_department(client, name="Product", headers=headers)

    created = client.post(
        "/api/v1/positions",
        json={
            "title": "Product Manager",
            "description": "Owns roadmap",
            "department_id": department["id"],
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["title"] == "Product Manager"
    assert body["department"] == "Product"

    listing = client.get("/api/v1/positions", headers=headers)
    assert listing.status_code == 200
    assert any(item["id"] == body["id"] for item in listing.json())


def test_cannot_delete_assigned_position(client):
    headers = auth_header(client)
    department = create_department(client, name="Ops")
    position = client.post(
        "/api/v1/positions",
        json={"title": "Ops Lead"},
        headers=headers,
    ).json()
    employee = client.post(
        "/api/v1/employees",
        json={
            "first_name": "Omar",
            "last_name": "Ops",
            "email": "omar.ops@test.com",
            "phone": "+216 20 333 444",
            "department_id": department["id"],
            "position_id": position["id"],
            "hire_date": "2024-02-01",
        },
        headers=headers,
    )
    assert employee.status_code == 201, employee.text

    deleted = client.delete(f"/api/v1/positions/{position['id']}", headers=headers)
    assert deleted.status_code == 409


def test_employee_cannot_create_position(client, db_session):
    create_user_with_role(
        db_session, email="emp.pos@test.com", password="emppass123", role_name="employee"
    )
    headers = auth_header(client, "emp.pos@test.com", "emppass123")
    response = client.post(
        "/api/v1/positions",
        json={"title": "Should Fail"},
        headers=headers,
    )
    assert response.status_code == 403
