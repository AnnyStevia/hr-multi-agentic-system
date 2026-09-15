from app.tests.helpers import auth_header, create_user_with_role
from app.tests.integration.test_applications import (
    _apply_form,
    _candidate_headers,
    _create_published_job,
    _mock_storage,
    _use_storage,
)


def _submit_application(client, db_session, *, cover=False, email="review.candidate@test.com"):
    storage = _mock_storage()
    _use_storage(client, storage)
    job = _create_published_job(client)
    candidate_headers = _candidate_headers(client, db_session, email=email)
    data, files = _apply_form(job, cover=cover)
    created = client.post(
        f"/api/v1/careers/jobs/{job['id']}/applications",
        data=data,
        files=files,
        headers=candidate_headers,
    )
    assert created.status_code == 201, created.text
    return created.json(), job, candidate_headers, storage


def _hr_headers(client, db_session):
    create_user_with_role(
        db_session,
        email="hr.review@test.com",
        password="hrpass123",
        role_name="hr",
    )
    return auth_header(client, "hr.review@test.com", "hrpass123")


def test_hr_user_can_view_application(client, db_session):
    application, _job, _candidate_headers, _storage = _submit_application(client, db_session)
    response = client.get(
        f"/api/v1/applications/{application['id']}",
        headers=_hr_headers(client, db_session),
    )
    assert response.status_code == 200
    assert response.json()["id"] == application["id"]
    assert response.json()["candidate"]["email"] == "review.candidate@test.com"


def test_admin_can_view_application(client, db_session):
    application, _job, _candidate_headers, _storage = _submit_application(client, db_session)
    response = client.get(
        f"/api/v1/applications/{application['id']}",
        headers=auth_header(client),
    )
    assert response.status_code == 200
    assert response.json()["id"] == application["id"]


def test_unauthenticated_cannot_view_application(client, db_session):
    application, _job, _candidate_headers, _storage = _submit_application(client, db_session)
    response = client.get(f"/api/v1/applications/{application['id']}")
    assert response.status_code == 401


def test_employee_cannot_view_application(client, db_session):
    application, _job, _candidate_headers, _storage = _submit_application(client, db_session)
    create_user_with_role(
        db_session,
        email="employee.review@test.com",
        password="emppass123",
        role_name="employee",
    )
    response = client.get(
        f"/api/v1/applications/{application['id']}",
        headers=auth_header(client, "employee.review@test.com", "emppass123"),
    )
    assert response.status_code == 403


def test_candidate_cannot_view_another_candidate_application(client, db_session):
    application, _job, _first_headers, _storage = _submit_application(
        client,
        db_session,
        email="first.review@test.com",
    )
    other_headers = _candidate_headers(client, db_session, email="second.review@test.com")
    own_path = client.get(
        f"/api/v1/careers/applications/{application['id']}",
        headers=other_headers,
    )
    hr_path = client.get(
        f"/api/v1/applications/{application['id']}",
        headers=other_headers,
    )
    assert own_path.status_code == 404
    assert hr_path.status_code == 403


def test_unauthorized_cannot_request_document_url(client, db_session):
    application, _job, candidate_headers, _storage = _submit_application(
        client,
        db_session,
        cover=True,
    )
    document_id = application["documents"][0]["id"]
    url = f"/api/v1/applications/{application['id']}/documents/{document_id}/url"
    assert client.get(url).status_code == 401
    assert client.get(url, headers=candidate_headers).status_code == 403


def test_authorized_hr_can_request_document_url(client, db_session):
    application, _job, _candidate_headers, storage = _submit_application(
        client,
        db_session,
        cover=True,
    )
    document_id = next(doc["id"] for doc in application["documents"] if doc["kind"] == "cv")
    response = client.get(
        f"/api/v1/applications/{application['id']}/documents/{document_id}/url",
        headers=_hr_headers(client, db_session),
    )
    assert response.status_code == 200
    assert response.json()["url"] == "https://s3.example/tmp"
    storage.generate_presigned_url.assert_called()


def test_candidate_cannot_change_application_status(client, db_session):
    application, _job, candidate_headers, _storage = _submit_application(client, db_session)
    response = client.patch(
        f"/api/v1/applications/{application['id']}/status",
        json={"status": "screening"},
        headers=candidate_headers,
    )
    assert response.status_code == 403


def test_invalid_status_is_rejected(client, db_session):
    application, _job, _candidate_headers, _storage = _submit_application(client, db_session)
    response = client.patch(
        f"/api/v1/applications/{application['id']}/status",
        json={"status": "interview"},
        headers=auth_header(client),
    )
    assert response.status_code == 422
