import json
from unittest.mock import MagicMock

from app.modules.recruitment.models import Application, ApplicationDocument, DocumentKind
from app.shared.storage import get_storage_service
from app.shared.storage.base import StoredObject
from app.tests.helpers import auth_header, create_candidate_user, create_department, job_payload

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"

QUESTIONS = [
    {
        "prompt": "How many years of Python experience do you have?",
        "question_type": "number",
        "required": True,
        "display_order": 0,
    },
    {
        "prompt": "Are you willing to relocate?",
        "question_type": "yes_no",
        "required": False,
        "display_order": 1,
    },
]

EDUCATION = [{"institution": "INSAT", "degree": "Engineering", "field_of_study": "Software", "start_year": 2020, "end_year": 2025}]
EXPERIENCE = [{"company": "Acme", "title": "Intern", "start_year": 2024, "description": "Backend work"}]


def _mock_storage() -> MagicMock:
    storage = MagicMock()
    storage.upload_file.return_value = StoredObject(key="k", bucket="b", content_type="application/pdf")
    storage.generate_presigned_url.return_value = "https://s3.example/tmp"
    return storage


def _use_storage(client, storage: MagicMock) -> None:
    client.app.dependency_overrides[get_storage_service] = lambda: storage


def _job_payload(client) -> dict:
    department = create_department(client)
    return job_payload(
        department["id"],
        title="Backend Engineer",
        description="Build APIs.",
        questions=QUESTIONS,
    )


def _create_published_job(client, payload=None) -> dict:
    headers = auth_header(client)
    created = client.post("/api/v1/jobs", json=payload or _job_payload(client), headers=headers)
    assert created.status_code == 201, created.text
    published = client.post(f"/api/v1/jobs/{created.json()['id']}/publish", headers=headers)
    assert published.status_code == 200
    return published.json()


def _candidate_headers(client, db_session, email="lina.apply@test.com"):
    create_candidate_user(db_session, email=email, password="candidate123")
    return auth_header(client, email, "candidate123")


def _apply_form(job, *, answers=None, cv_name="cv.pdf", cv_body=PDF, cover=False):
    question_id = job["questions"][0]["id"]
    data = {
        "education": json.dumps(EDUCATION),
        "experience": json.dumps(EXPERIENCE),
        "answers": json.dumps(answers if answers is not None else [{"question_id": question_id, "value": "3"}]),
        "phone": "+216 20 123 456",
    }
    files = {"cv": (cv_name, cv_body, "application/pdf")}
    if cover:
        files["cover_letter"] = ("letter.pdf", PDF, "application/pdf")
    return data, files


def test_candidate_can_apply_to_published_job(client, db_session):
    storage = _mock_storage()
    _use_storage(client, storage)
    job = _create_published_job(client)
    headers = _candidate_headers(client, db_session)
    data, files = _apply_form(job, cover=True)

    response = client.post(
        f"/api/v1/careers/jobs/{job['id']}/applications",
        data=data,
        files=files,
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "submitted"
    assert body["candidate"]["email"] == "lina.apply@test.com"
    assert body["candidate"]["phone"] == "+216 20 123 456"
    assert body["job"]["title"] == "Backend Engineer"
    assert any(doc["kind"] == "cv" for doc in body["documents"])
    assert any(doc["kind"] == "cover_letter" for doc in body["documents"])
    assert "storage_key" not in str(body)
    assert storage.upload_file.call_count == 2

    application = db_session.query(Application).one()
    documents = db_session.query(ApplicationDocument).all()
    assert len(documents) == 2
    cv = next(doc for doc in documents if doc.kind == DocumentKind.CV)
    assert cv.storage_key == f"applications/{application.id}/cv/{cv.id}.pdf"
    assert cv.original_filename == "cv.pdf"


def test_cannot_apply_to_unpublished_job(client, db_session):
    storage = _mock_storage()
    _use_storage(client, storage)
    headers_admin = auth_header(client)
    draft = client.post("/api/v1/jobs", json=_job_payload(client), headers=headers_admin)
    job = draft.json()
    headers = _candidate_headers(client, db_session)
    data, files = _apply_form(job)

    response = client.post(
        f"/api/v1/careers/jobs/{job['id']}/applications",
        data=data,
        files=files,
        headers=headers,
    )
    assert response.status_code == 404
    storage.upload_file.assert_not_called()


def test_cannot_apply_twice_to_same_job(client, db_session):
    storage = _mock_storage()
    _use_storage(client, storage)
    job = _create_published_job(client)
    headers = _candidate_headers(client, db_session)
    data, files = _apply_form(job)
    first = client.post(
        f"/api/v1/careers/jobs/{job['id']}/applications",
        data=data,
        files=files,
        headers=headers,
    )
    assert first.status_code == 201
    second = client.post(
        f"/api/v1/careers/jobs/{job['id']}/applications",
        data=data,
        files=files,
        headers=headers,
    )
    assert second.status_code == 409
    assert db_session.query(Application).count() == 1


def test_required_question_must_be_answered(client, db_session):
    storage = _mock_storage()
    _use_storage(client, storage)
    job = _create_published_job(client)
    headers = _candidate_headers(client, db_session)
    data, files = _apply_form(job, answers=[])
    response = client.post(
        f"/api/v1/careers/jobs/{job['id']}/applications",
        data=data,
        files=files,
        headers=headers,
    )
    assert response.status_code == 400
    storage.upload_file.assert_not_called()


def test_phone_is_required_on_apply(client, db_session):
    storage = _mock_storage()
    _use_storage(client, storage)
    job = _create_published_job(client)
    headers = _candidate_headers(client, db_session)
    data, files = _apply_form(job)
    data["phone"] = "123"
    response = client.post(
        f"/api/v1/careers/jobs/{job['id']}/applications",
        data=data,
        files=files,
        headers=headers,
    )
    assert response.status_code == 400
    storage.upload_file.assert_not_called()
    storage = _mock_storage()
    _use_storage(client, storage)
    job = _create_published_job(client)
    first_headers = _candidate_headers(client, db_session, email="first@test.com")
    data, files = _apply_form(job)
    created = client.post(
        f"/api/v1/careers/jobs/{job['id']}/applications",
        data=data,
        files=files,
        headers=first_headers,
    )
    application_id = created.json()["id"]

    second_headers = _candidate_headers(client, db_session, email="second@test.com")
    response = client.get(f"/api/v1/careers/applications/{application_id}", headers=second_headers)
    assert response.status_code == 404


def test_invalid_file_type_is_rejected(client, db_session):
    storage = _mock_storage()
    _use_storage(client, storage)
    job = _create_published_job(client)
    headers = _candidate_headers(client, db_session)
    data, _files = _apply_form(job)
    response = client.post(
        f"/api/v1/careers/jobs/{job['id']}/applications",
        data=data,
        files={"cv": ("virus.exe", b"MZ\x90\x00", "application/octet-stream")},
        headers=headers,
    )
    assert response.status_code == 400
    storage.upload_file.assert_not_called()


def test_oversized_file_is_rejected(client, db_session):
    storage = _mock_storage()
    _use_storage(client, storage)
    job = _create_published_job(client)
    headers = _candidate_headers(client, db_session)
    data, _files = _apply_form(job)
    huge = PDF + (b"0" * (5 * 1024 * 1024 + 1))
    response = client.post(
        f"/api/v1/careers/jobs/{job['id']}/applications",
        data=data,
        files={"cv": ("cv.pdf", huge, "application/pdf")},
        headers=headers,
    )
    assert response.status_code == 413
    storage.upload_file.assert_not_called()


def test_hr_can_list_and_open_application_documents(client, db_session):
    storage = _mock_storage()
    _use_storage(client, storage)
    job = _create_published_job(client)
    headers = _candidate_headers(client, db_session)
    data, files = _apply_form(job, cover=True)
    created = client.post(
        f"/api/v1/careers/jobs/{job['id']}/applications",
        data=data,
        files=files,
        headers=headers,
    )
    application_id = created.json()["id"]
    document_id = created.json()["documents"][0]["id"]

    hr_headers = auth_header(client)
    listing = client.get(f"/api/v1/jobs/{job['id']}/applications", headers=hr_headers)
    assert listing.status_code == 200
    assert listing.json()[0]["candidate"]["email"] == "lina.apply@test.com"
    assert listing.json()[0]["has_cv"] is True

    detail = client.get(f"/api/v1/applications/{application_id}", headers=hr_headers)
    assert detail.status_code == 200
    assert detail.json()["education"][0]["institution"] == "INSAT"

    url = client.get(
        f"/api/v1/applications/{application_id}/documents/{document_id}/url",
        headers=hr_headers,
    )
    assert url.status_code == 200
    assert url.json()["url"] == "https://s3.example/tmp"
    assert url.json()["download"] is False
    assert url.json()["content_type"]
    storage.generate_presigned_url.assert_called_once()
    assert storage.generate_presigned_url.call_args.kwargs["download"] is False

    download = client.get(
        f"/api/v1/applications/{application_id}/documents/{document_id}/url?download=true",
        headers=hr_headers,
    )
    assert download.status_code == 200
    assert download.json()["download"] is True
    assert storage.generate_presigned_url.call_args.kwargs["download"] is True


def test_hr_can_update_application_status(client, db_session):
    storage = _mock_storage()
    _use_storage(client, storage)
    job = _create_published_job(client)
    headers = _candidate_headers(client, db_session)
    data, files = _apply_form(job)
    created = client.post(
        f"/api/v1/careers/jobs/{job['id']}/applications",
        data=data,
        files=files,
        headers=headers,
    )
    application_id = created.json()["id"]
    assert created.json()["status"] == "submitted"

    hr_headers = auth_header(client)
    updated = client.patch(
        f"/api/v1/applications/{application_id}/status",
        json={"status": "screening"},
        headers=hr_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "screening"

    listing = client.get(f"/api/v1/jobs/{job['id']}/applications", headers=hr_headers)
    assert listing.json()[0]["status"] == "screening"


def test_candidate_cannot_update_application_status(client, db_session):
    storage = _mock_storage()
    _use_storage(client, storage)
    job = _create_published_job(client)
    headers = _candidate_headers(client, db_session)
    data, files = _apply_form(job)
    created = client.post(
        f"/api/v1/careers/jobs/{job['id']}/applications",
        data=data,
        files=files,
        headers=headers,
    )
    application_id = created.json()["id"]
    response = client.patch(
        f"/api/v1/applications/{application_id}/status",
        json={"status": "screening"},
        headers=headers,
    )
    assert response.status_code == 403


def test_invalid_application_status_is_rejected(client, db_session):
    storage = _mock_storage()
    _use_storage(client, storage)
    job = _create_published_job(client)
    headers = _candidate_headers(client, db_session)
    data, files = _apply_form(job)
    created = client.post(
        f"/api/v1/careers/jobs/{job['id']}/applications",
        data=data,
        files=files,
        headers=headers,
    )
    response = client.patch(
        f"/api/v1/applications/{created.json()['id']}/status",
        json={"status": "not-a-status"},
        headers=auth_header(client),
    )
    assert response.status_code == 422


def test_candidate_cannot_access_hr_application_endpoints(client, db_session):
    storage = _mock_storage()
    _use_storage(client, storage)
    job = _create_published_job(client)
    headers = _candidate_headers(client, db_session)
    data, files = _apply_form(job)
    created = client.post(
        f"/api/v1/careers/jobs/{job['id']}/applications",
        data=data,
        files=files,
        headers=headers,
    )
    application_id = created.json()["id"]
    assert client.get(f"/api/v1/jobs/{job['id']}/applications", headers=headers).status_code == 403
    assert client.get(f"/api/v1/applications/{application_id}", headers=headers).status_code == 403


def test_create_job_persists_questions(client):
    response = client.post("/api/v1/jobs", json=_job_payload(client), headers=auth_header(client))
    assert response.status_code == 201
    questions = response.json()["questions"]
    assert len(questions) == 2
    assert questions[0]["question_type"] == "number"
    assert questions[0]["required"] is True
