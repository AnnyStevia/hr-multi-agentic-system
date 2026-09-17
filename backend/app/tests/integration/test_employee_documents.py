from unittest.mock import MagicMock

from app.modules.documents.models import Document
from app.shared.storage import get_storage_service
from app.shared.storage.base import StoredObject
from app.tests.helpers import auth_header, create_candidate_user, create_user_with_role
from app.tests.integration.test_onboarding import _hire

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
EXE = b"MZ" + b"\x00" * 32


def _mock_storage() -> MagicMock:
    storage = MagicMock()
    storage.upload_file.return_value = StoredObject(
        key="k", bucket="b", content_type="application/pdf"
    )
    storage.generate_presigned_url.return_value = "https://s3.example/presigned"
    return storage


def _use_storage(client, storage: MagicMock) -> None:
    client.app.dependency_overrides[get_storage_service] = lambda: storage


def _upload_pdf(
    client,
    *,
    url: str,
    headers: dict,
    document_type: str = "id_document",
    filename: str = "id.pdf",
    content: bytes = PDF,
):
    return client.post(
        url,
        headers=headers,
        data={"document_type": document_type},
        files={"file": (filename, content, "application/pdf")},
    )


def test_employee_can_upload_and_list_own_documents(client, db_session):
    _application, _job, candidate_headers, _headers, body = _hire(
        client, db_session, email="docs.own@test.com"
    )
    storage = _mock_storage()
    _use_storage(client, storage)
    employee_id = body["hired_employee_id"]

    created = _upload_pdf(client, url="/api/v1/me/documents", headers=candidate_headers)
    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload["document_type"] == "id_document"
    assert payload["original_filename"] == "id.pdf"
    assert payload["employee_id"] == employee_id
    assert "storage_key" not in payload
    assert "aws" not in created.text.lower()

    storage.upload_file.assert_called()
    uploaded_key = storage.upload_file.call_args.args[0]
    assert uploaded_key.startswith(f"employees/{employee_id}/documents/")
    assert uploaded_key.endswith("/id.pdf")

    listed = client.get("/api/v1/me/documents", headers=candidate_headers)
    assert listed.status_code == 200, listed.text
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == payload["id"]
    assert "storage_key" not in listed.json()[0]


def test_employee_cannot_access_another_employees_documents(client, db_session):
    _a, _j, owner_headers, headers, body = _hire(
        client, db_session, email="docs.owner@test.com"
    )
    storage = _mock_storage()
    _use_storage(client, storage)
    employee_id = body["hired_employee_id"]
    created = _upload_pdf(client, url="/api/v1/me/documents", headers=owner_headers)
    assert created.status_code == 201, created.text
    document_id = created.json()["id"]

    other = create_candidate_user(
        db_session, email="docs.other@test.com", password="otherpass123"
    )
    other_headers = auth_header(client, email=other.email, password="otherpass123")

    assert (
        client.get(f"/api/v1/me/documents/{document_id}/url", headers=other_headers).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/employees/{employee_id}/documents",
            headers=other_headers,
        ).status_code
        == 403
    )
    assert headers is not None


def test_hr_can_list_upload_presign_and_delete(client, db_session):
    _a, _j, candidate_headers, headers, body = _hire(
        client, db_session, email="docs.hr@test.com"
    )
    storage = _mock_storage()
    _use_storage(client, storage)
    employee_id = body["hired_employee_id"]

    uploaded = _upload_pdf(
        client,
        url=f"/api/v1/employees/{employee_id}/documents",
        headers=headers,
        document_type="contract",
        filename="contract.pdf",
    )
    assert uploaded.status_code == 201, uploaded.text
    document_id = uploaded.json()["id"]
    assert uploaded.json()["document_type"] == "contract"

    listed = client.get(f"/api/v1/employees/{employee_id}/documents", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    url_resp = client.get(
        f"/api/v1/employees/{employee_id}/documents/{document_id}/url",
        headers=headers,
    )
    assert url_resp.status_code == 200, url_resp.text
    assert url_resp.json()["url"] == "https://s3.example/presigned"
    storage.generate_presigned_url.assert_called()
    key_arg = storage.generate_presigned_url.call_args.args[0]
    assert key_arg.startswith(f"employees/{employee_id}/documents/{document_id}/")

    me_url = client.get(
        f"/api/v1/me/documents/{document_id}/url?download=true",
        headers=candidate_headers,
    )
    assert me_url.status_code == 200
    assert me_url.json()["download"] is True

    deleted = client.delete(
        f"/api/v1/employees/{employee_id}/documents/{document_id}",
        headers=headers,
    )
    assert deleted.status_code == 204
    storage.delete_file.assert_called()
    assert client.get(f"/api/v1/employees/{employee_id}/documents", headers=headers).json() == []


def test_unauthorized_document_url_rejected(client, db_session):
    _a, _j, _cand, headers, body = _hire(client, db_session, email="docs.unauth@test.com")
    storage = _mock_storage()
    _use_storage(client, storage)
    employee_id = body["hired_employee_id"]
    created = _upload_pdf(
        client,
        url=f"/api/v1/employees/{employee_id}/documents",
        headers=headers,
    )
    document_id = created.json()["id"]

    assert client.get(f"/api/v1/me/documents/{document_id}/url").status_code == 401
    assert (
        client.get(
            f"/api/v1/employees/{employee_id}/documents/{document_id}/url"
        ).status_code
        == 401
    )

    create_user_with_role(
        db_session,
        email="docs.plain.emp@test.com",
        password="emppass123",
        role_name="employee",
    )
    plain = auth_header(client, email="docs.plain.emp@test.com", password="emppass123")
    assert (
        client.get(
            f"/api/v1/employees/{employee_id}/documents/{document_id}/url",
            headers=plain,
        ).status_code
        == 403
    )


def test_invalid_and_oversized_files_rejected(client, db_session):
    _a, _j, candidate_headers, _headers, _body = _hire(
        client, db_session, email="docs.invalid@test.com"
    )
    storage = _mock_storage()
    _use_storage(client, storage)

    invalid = client.post(
        "/api/v1/me/documents",
        headers=candidate_headers,
        data={"document_type": "other"},
        files={"file": ("virus.exe", EXE, "application/octet-stream")},
    )
    assert invalid.status_code == 400

    oversized = client.post(
        "/api/v1/me/documents",
        headers=candidate_headers,
        data={"document_type": "other"},
        files={"file": ("big.pdf", b"%PDF" + b"x" * (5 * 1024 * 1024 + 10), "application/pdf")},
    )
    assert oversized.status_code == 413
    storage.upload_file.assert_not_called()


def test_candidate_without_employee_cannot_upload(client, db_session):
    storage = _mock_storage()
    _use_storage(client, storage)
    create_candidate_user(db_session, email="docs.purecand@test.com", password="candpass123")
    headers = auth_header(client, email="docs.purecand@test.com", password="candpass123")
    response = _upload_pdf(client, url="/api/v1/me/documents", headers=headers)
    assert response.status_code == 404


def test_employee_cannot_delete_via_hr_endpoint_without_permission(client, db_session):
    _a, _j, candidate_headers, headers, body = _hire(
        client, db_session, email="docs.nodelete@test.com"
    )
    storage = _mock_storage()
    _use_storage(client, storage)
    employee_id = body["hired_employee_id"]
    created = _upload_pdf(client, url="/api/v1/me/documents", headers=candidate_headers)
    document_id = created.json()["id"]

    assert (
        client.delete(
            f"/api/v1/employees/{employee_id}/documents/{document_id}",
            headers=candidate_headers,
        ).status_code
        == 403
    )
    assert db_session.query(Document).filter(Document.id == document_id).count() == 1

    assert (
        client.delete(
            f"/api/v1/employees/{employee_id}/documents/{document_id}",
            headers=headers,
        ).status_code
        == 204
    )
