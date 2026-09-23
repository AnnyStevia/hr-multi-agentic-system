from datetime import date
from unittest.mock import MagicMock

from app.core.security import get_password_hash
from app.modules.employees.models import Employee, EmploymentStatus
from app.modules.identity.models import Role, User, UserRole
from app.shared.storage import get_storage_service
from app.shared.storage.base import StoredObject
from app.tests.helpers import auth_header, create_department, hr_payload
from app.tests.integration.test_onboarding import _hire

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"


def _mock_storage() -> MagicMock:
    storage = MagicMock()
    storage.upload_file.return_value = StoredObject(
        key="k", bucket="b", content_type="application/pdf"
    )
    storage.generate_presigned_url.return_value = "https://s3.example/presigned"
    return storage


def _use_storage(client, storage: MagicMock) -> None:
    client.app.dependency_overrides[get_storage_service] = lambda: storage


def _upload_private(client, headers: dict, *, title: str = "My Notes"):
    return client.post(
        "/api/v1/me/private-documents",
        headers=headers,
        data={"title": title, "description": "Personal only"},
        files={"file": ("notes.pdf", PDF, "application/pdf")},
    )


def _link_employee(
    db_session,
    *,
    email: str,
    password: str,
    role_name: str,
    department_id: int,
    first_name: str = "Pat",
    last_name: str = "Person",
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
    return user, employee


def test_employee_can_crud_own_private_documents(client, db_session):
    _application, _job, headers, _admin, body = _hire(
        client, db_session, email="private.owner@test.com"
    )
    storage = _mock_storage()
    _use_storage(client, storage)

    created = _upload_private(client, headers)
    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload["title"] == "My Notes"
    assert payload["owner_employee_id"] == body["hired_employee_id"]
    assert "storage_key" not in payload
    key = storage.upload_file.call_args.args[0]
    assert f"employees/{body['hired_employee_id']}/private/" in key

    listed = client.get("/api/v1/me/private-documents", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    updated = client.patch(
        f"/api/v1/me/private-documents/{payload['id']}",
        json={"title": "Renamed Notes"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Renamed Notes"

    url = client.get(
        f"/api/v1/me/private-documents/{payload['id']}/url",
        headers=headers,
    )
    assert url.status_code == 200
    assert url.json()["url"] == "https://s3.example/presigned"

    deleted = client.delete(
        f"/api/v1/me/private-documents/{payload['id']}",
        headers=headers,
    )
    assert deleted.status_code == 204
    assert client.get("/api/v1/me/private-documents", headers=headers).json() == []


def test_hr_and_admin_can_crud_own_private_documents(client, db_session):
    admin_headers = auth_header(client)
    department = create_department(client, name="Private Docs Dept")
    storage = _mock_storage()
    _use_storage(client, storage)

    # Give seeded admin an employee profile for private docs
    admin_user = (
        db_session.query(User).filter(User.email == "admin@test.com").one()
    )
    admin_employee = Employee(
        employee_number="PENDING",
        first_name="System",
        last_name="Admin",
        email="admin@test.com",
        phone="+21620999000",
        department_id=department["id"],
        position="Administrator",
        hire_date=date(2020, 1, 1),
        employment_status=EmploymentStatus.ACTIVE,
        user_id=admin_user.id,
    )
    db_session.add(admin_employee)
    db_session.flush()
    admin_employee.employee_number = f"EMP-{admin_employee.id:06d}"
    db_session.commit()

    admin_created = _upload_private(client, admin_headers, title="Admin Private")
    assert admin_created.status_code == 201, admin_created.text

    hr = client.post(
        "/api/v1/users/hr",
        json=hr_payload(department["id"], email="private.hr@test.com"),
        headers=admin_headers,
    )
    assert hr.status_code == 201, hr.text
    hr_headers = auth_header(client, "private.hr@test.com", "hrpass123")
    hr_created = _upload_private(client, hr_headers, title="HR Private")
    assert hr_created.status_code == 201, hr_created.text
    assert (
        client.get("/api/v1/me/private-documents", headers=hr_headers).json()[0]["title"]
        == "HR Private"
    )


def test_private_documents_idor_denied_across_roles(client, db_session):
    storage = _mock_storage()
    _use_storage(client, storage)
    department = create_department(client, name="IDOR Docs Dept")

    _a, _j, owner_headers, _hr_hire_headers, _body = _hire(
        client, db_session, email="private.idor.owner@test.com"
    )
    _use_storage(client, storage)
    admin_headers = auth_header(client)
    created = _upload_private(client, owner_headers, title="Secret")
    assert created.status_code == 201, created.text
    doc_id = created.json()["id"]

    _link_employee(
        db_session,
        email="private.idor.other@test.com",
        password="emppass123",
        role_name="employee",
        department_id=department["id"],
        first_name="Other",
        last_name="Emp",
    )
    other_emp_headers = auth_header(client, "private.idor.other@test.com", "emppass123")

    assert (
        client.get(
            f"/api/v1/me/private-documents/{doc_id}/url",
            headers=other_emp_headers,
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/v1/me/private-documents/{doc_id}",
            json={"title": "Stolen"},
            headers=other_emp_headers,
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/v1/me/private-documents/{doc_id}",
            headers=other_emp_headers,
        ).status_code
        == 404
    )

    hr = client.post(
        "/api/v1/users/hr",
        json=hr_payload(department["id"], email="private.idor.hr@test.com"),
        headers=admin_headers,
    )
    assert hr.status_code == 201, hr.text
    hr_headers = auth_header(client, "private.idor.hr@test.com", "hrpass123")
    assert (
        client.get(
            f"/api/v1/me/private-documents/{doc_id}/url",
            headers=hr_headers,
        ).status_code
        == 404
    )
    assert client.get("/api/v1/me/private-documents", headers=hr_headers).json() == []

    admin_user = db_session.query(User).filter(User.email == "admin@test.com").one()
    if db_session.query(Employee).filter(Employee.user_id == admin_user.id).first() is None:
        emp = Employee(
            employee_number="PENDING",
            first_name="System",
            last_name="Admin",
            email="admin@test.com",
            phone="+21620999111",
            department_id=department["id"],
            position="Administrator",
            hire_date=date(2020, 1, 1),
            employment_status=EmploymentStatus.ACTIVE,
            user_id=admin_user.id,
        )
        db_session.add(emp)
        db_session.flush()
        emp.employee_number = f"EMP-{emp.id:06d}"
        db_session.commit()

    assert (
        client.get(
            f"/api/v1/me/private-documents/{doc_id}/url",
            headers=admin_headers,
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/v1/me/private-documents/{doc_id}",
            headers=admin_headers,
        ).status_code
        == 404
    )


def test_existing_employee_documents_still_work(client, db_session):
    """Regression: onboarding/employee documents module unchanged."""
    _application, _job, headers, admin_headers, body = _hire(
        client, db_session, email="private.regression@test.com"
    )
    storage = _mock_storage()
    _use_storage(client, storage)
    employee_id = body["hired_employee_id"]

    created = client.post(
        "/api/v1/me/documents",
        headers=headers,
        data={"document_type": "id_document"},
        files={"file": ("id.pdf", PDF, "application/pdf")},
    )
    assert created.status_code == 201, created.text

    listed = client.get(
        f"/api/v1/employees/{employee_id}/documents",
        headers=admin_headers,
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1
