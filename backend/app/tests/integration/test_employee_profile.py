from unittest.mock import MagicMock

from app.modules.employees.models import Employee
from app.shared.storage import get_storage_service
from app.shared.storage.base import StoredObject
from app.tests.helpers import auth_header, create_candidate_user
from app.tests.integration.test_onboarding import _hire

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG = b"\xff\xd8\xff" + b"\x00" * 32
EXE = b"MZ" + b"\x00" * 32
HUGE = PNG + (b"\x00" * (2 * 1024 * 1024))


def _mock_storage() -> MagicMock:
    storage = MagicMock()
    storage.upload_file.return_value = StoredObject(
        key="k", bucket="b", content_type="image/png"
    )
    storage.generate_presigned_url.return_value = "https://s3.example/profile"
    return storage


def _use_storage(client, storage: MagicMock) -> None:
    client.app.dependency_overrides[get_storage_service] = lambda: storage


def test_employee_can_get_and_update_own_profile(client, db_session):
    _a, _j, candidate_headers, headers, body = _hire(
        client, db_session, email="profile.own@test.com"
    )
    me = client.get("/api/v1/me/profile", headers=candidate_headers)
    assert me.status_code == 200, me.text
    payload = me.json()
    assert payload["employee_id"] == body["hired_employee_id"]
    assert payload["email"] == "profile.own@test.com"
    assert "profile_picture_storage_key" not in payload
    assert headers is not None

    updated = client.patch(
        "/api/v1/me/profile",
        headers=candidate_headers,
        json={
            "phone": "+216 20 999 888",
            "date_of_birth": "1995-05-10",
            "address": "12 Rue Test",
            "city": "Tunis",
            "country": "Tunisia",
        },
    )
    assert updated.status_code == 200, updated.text
    data = updated.json()
    assert data["phone"] == "+216 20 999 888"
    assert data["date_of_birth"] == "1995-05-10"
    assert data["address"] == "12 Rue Test"
    assert data["city"] == "Tunis"
    assert data["country"] == "Tunisia"


def test_employee_cannot_update_another_profile(client, db_session):
    _a, _j, owner_headers, _headers, body = _hire(
        client, db_session, email="profile.owner@test.com"
    )
    other = create_candidate_user(
        db_session, email="profile.other@test.com", password="otherpass123"
    )
    other_headers = auth_header(client, email=other.email, password="otherpass123")

    assert client.get("/api/v1/me/profile", headers=other_headers).status_code == 404
    assert (
        client.patch(
            "/api/v1/me/profile",
            headers=other_headers,
            json={"city": "Sfax"},
        ).status_code
        == 404
    )
    assert owner_headers is not None
    assert body["hired_employee_id"] is not None


def test_profile_picture_upload_url_delete_and_validation(client, db_session):
    _a, _j, candidate_headers, headers, body = _hire(
        client, db_session, email="profile.pic@test.com"
    )
    storage = _mock_storage()
    _use_storage(client, storage)

    bad_type = client.post(
        "/api/v1/me/profile/picture",
        headers=candidate_headers,
        files={"file": ("virus.exe", EXE, "application/octet-stream")},
    )
    assert bad_type.status_code == 400

    too_big = client.post(
        "/api/v1/me/profile/picture",
        headers=candidate_headers,
        files={"file": ("big.png", HUGE, "image/png")},
    )
    assert too_big.status_code == 413

    uploaded = client.post(
        "/api/v1/me/profile/picture",
        headers=candidate_headers,
        files={"file": ("avatar.png", PNG, "image/png")},
    )
    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["has_profile_picture"] is True
    assert "storage_key" not in uploaded.json()
    storage.upload_file.assert_called()
    key_arg = storage.upload_file.call_args[0][0]
    assert key_arg.startswith(f"employees/{body['hired_employee_id']}/profile-picture/")

    url = client.get("/api/v1/me/profile/picture/url", headers=candidate_headers)
    assert url.status_code == 200, url.text
    assert url.json()["url"] == "https://s3.example/profile"

    other = create_candidate_user(
        db_session, email="profile.pic.other@test.com", password="otherpass123"
    )
    other_headers = auth_header(client, email=other.email, password="otherpass123")
    assert client.get("/api/v1/me/profile/picture/url", headers=other_headers).status_code == 404

    hr_url = client.get(
        f"/api/v1/employees/{body['hired_employee_id']}/profile/picture/url",
        headers=headers,
    )
    assert hr_url.status_code == 200

    deleted = client.delete("/api/v1/me/profile/picture", headers=candidate_headers)
    assert deleted.status_code == 204
    assert client.get("/api/v1/me/profile/picture/url", headers=candidate_headers).status_code == 404
    employee = db_session.query(Employee).filter(Employee.id == body["hired_employee_id"]).one()
    assert employee.profile_picture_storage_key is None


def test_education_and_experience_crud_ownership_and_dates(client, db_session):
    _a, _j, candidate_headers, headers, body = _hire(
        client, db_session, email="profile.edu@test.com"
    )
    employee_id = body["hired_employee_id"]

    bad_dates = client.post(
        "/api/v1/me/profile/education",
        headers=candidate_headers,
        json={
            "institution": "ENIT",
            "degree": "Engineering",
            "field_of_study": "CS",
            "start_date": "2020-01-01",
            "end_date": "2019-01-01",
        },
    )
    assert bad_dates.status_code == 400

    created = client.post(
        "/api/v1/me/profile/education",
        headers=candidate_headers,
        json={
            "institution": "ENIT",
            "degree": "Engineering",
            "field_of_study": "Computer Science",
            "start_date": "2018-09-01",
            "end_date": "2022-06-30",
            "description": "Final year project",
        },
    )
    assert created.status_code == 201, created.text
    edu_id = created.json()["id"]

    patched = client.patch(
        f"/api/v1/me/profile/education/{edu_id}",
        headers=candidate_headers,
        json={"degree": "Software Engineering"},
    )
    assert patched.status_code == 200
    assert patched.json()["degree"] == "Software Engineering"

    listed = client.get("/api/v1/me/profile/education", headers=candidate_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    hr_edu = client.get(
        f"/api/v1/employees/{employee_id}/profile/education",
        headers=headers,
    )
    assert hr_edu.status_code == 200
    assert len(hr_edu.json()) == 1

    other = create_candidate_user(
        db_session, email="profile.edu.other@test.com", password="otherpass123"
    )
    other_headers = auth_header(client, email=other.email, password="otherpass123")
    assert (
        client.patch(
            f"/api/v1/me/profile/education/{edu_id}",
            headers=other_headers,
            json={"degree": "Hacked"},
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/v1/me/profile/education/{edu_id}",
            headers=other_headers,
        ).status_code
        == 404
    )

    assert (
        client.delete(
            f"/api/v1/me/profile/education/{edu_id}",
            headers=candidate_headers,
        ).status_code
        == 204
    )
    assert client.get("/api/v1/me/profile/education", headers=candidate_headers).json() == []

    bad_exp = client.post(
        "/api/v1/me/profile/experience",
        headers=candidate_headers,
        json={
            "company": "Acme",
            "position": "Dev",
            "start_date": "2023-01-01",
            "end_date": "2022-01-01",
        },
    )
    assert bad_exp.status_code == 400

    exp = client.post(
        "/api/v1/me/profile/experience",
        headers=candidate_headers,
        json={
            "company": "Acme",
            "position": "Developer",
            "start_date": "2023-01-01",
            "end_date": None,
            "description": "Backend work",
        },
    )
    assert exp.status_code == 201, exp.text
    exp_id = exp.json()["id"]

    updated_exp = client.patch(
        f"/api/v1/me/profile/experience/{exp_id}",
        headers=candidate_headers,
        json={"position": "Senior Developer"},
    )
    assert updated_exp.status_code == 200
    assert updated_exp.json()["position"] == "Senior Developer"
    assert updated_exp.json()["end_date"] is None

    assert (
        client.patch(
            f"/api/v1/me/profile/experience/{exp_id}",
            headers=other_headers,
            json={"company": "Nope"},
        ).status_code
        == 404
    )

    hr_exp = client.get(
        f"/api/v1/employees/{employee_id}/profile/experience",
        headers=headers,
    )
    assert hr_exp.status_code == 200
    assert len(hr_exp.json()) == 1

    assert (
        client.delete(
            f"/api/v1/me/profile/experience/{exp_id}",
            headers=candidate_headers,
        ).status_code
        == 204
    )


def test_hr_can_view_employee_profile(client, db_session):
    _a, _j, candidate_headers, headers, body = _hire(
        client, db_session, email="profile.hrview@test.com"
    )
    client.patch(
        "/api/v1/me/profile",
        headers=candidate_headers,
        json={"city": "Sousse", "country": "Tunisia", "address": "1 Avenue"},
    )
    response = client.get(
        f"/api/v1/employees/{body['hired_employee_id']}/profile",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["city"] == "Sousse"
    assert data["employee_id"] == body["hired_employee_id"]
    assert "profile_picture_storage_key" not in data

    assert (
        client.get(
            f"/api/v1/employees/{body['hired_employee_id']}/profile",
            headers=candidate_headers,
        ).status_code
        == 403
    )
