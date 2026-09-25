from unittest.mock import MagicMock

import pytest

from app.modules.documents.models import CompanyDocumentCategory
from app.shared.storage import get_storage_service
from app.shared.storage.base import StoredObject
from app.tests.helpers import auth_header, create_department, create_user_with_role, hr_payload
from app.tests.integration.test_onboarding import _hire

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"


@pytest.fixture(autouse=True)
def _disable_background_rag_indexing(monkeypatch):
    """Unit/integration API tests must not call Gemini via BackgroundTasks."""
    monkeypatch.setattr(
        "app.api.v1.library_documents.run_company_document_indexing",
        lambda _document_id: None,
    )


def _mock_storage() -> MagicMock:
    storage = MagicMock()
    storage.upload_file.return_value = StoredObject(
        key="k", bucket="b", content_type="application/pdf"
    )
    storage.generate_presigned_url.return_value = "https://s3.example/presigned"
    return storage


def _use_storage(client, storage: MagicMock) -> None:
    client.app.dependency_overrides[get_storage_service] = lambda: storage


def _category_id(db_session, slug: str = "hr_policies") -> int:
    category = (
        db_session.query(CompanyDocumentCategory)
        .filter(CompanyDocumentCategory.slug == slug)
        .one()
    )
    return category.id


def _upload_company(client, headers: dict, *, category_id: int, title: str = "Handbook"):
    return client.post(
        "/api/v1/company-documents",
        headers=headers,
        data={
            "title": title,
            "description": "Company rules",
            "category_id": str(category_id),
        },
        files={"file": ("handbook.pdf", PDF, "application/pdf")},
    )


def test_hr_and_admin_can_upload_company_document(client, db_session):
    headers = auth_header(client)
    storage = _mock_storage()
    _use_storage(client, storage)
    category_id = _category_id(db_session)

    created = _upload_company(client, headers, category_id=category_id)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["title"] == "Handbook"
    assert body["category_id"] == category_id
    assert body["category_label"] == "HR Policies"
    assert body["status"] == "active"
    assert body["version"] == 1
    assert "storage_key" not in body
    uploaded_key = storage.upload_file.call_args.args[0]
    assert uploaded_key.startswith("company-documents/")
    assert uploaded_key.endswith("/handbook.pdf")

    department = create_department(client, name="Docs HR Dept")
    hr = client.post(
        "/api/v1/users/hr",
        json=hr_payload(department["id"], email="docs.hr@test.com"),
        headers=headers,
    )
    assert hr.status_code == 201, hr.text
    hr_headers = auth_header(client, "docs.hr@test.com", "hrpass123")
    hr_upload = _upload_company(
        client, hr_headers, category_id=category_id, title="HR Policy"
    )
    assert hr_upload.status_code == 201, hr_upload.text


def test_company_upload_requires_category(client, db_session):
    headers = auth_header(client)
    _use_storage(client, _mock_storage())
    response = client.post(
        "/api/v1/company-documents",
        headers=headers,
        data={"title": "No Category"},
        files={"file": ("handbook.pdf", PDF, "application/pdf")},
    )
    assert response.status_code == 422


def test_employee_can_view_and_download_but_not_manage(client, db_session):
    admin_headers = auth_header(client)
    storage = _mock_storage()
    _use_storage(client, storage)
    category_id = _category_id(db_session)
    created = _upload_company(client, admin_headers, category_id=category_id)
    assert created.status_code == 201, created.text
    doc_id = created.json()["id"]

    _application, _job, employee_headers, _headers, _body = _hire(
        client, db_session, email="docs.library.emp@test.com"
    )
    _use_storage(client, storage)

    listed = client.get("/api/v1/company-documents", headers=employee_headers)
    assert listed.status_code == 200, listed.text
    assert any(item["id"] == doc_id for item in listed.json())

    url = client.get(
        f"/api/v1/company-documents/{doc_id}/url?download=true",
        headers=employee_headers,
    )
    assert url.status_code == 200, url.text
    assert url.json()["url"] == "https://s3.example/presigned"
    assert url.json()["download"] is True

    blocked_upload = _upload_company(
        client, employee_headers, category_id=category_id, title="Blocked"
    )
    assert blocked_upload.status_code == 403

    blocked_patch = client.patch(
        f"/api/v1/company-documents/{doc_id}",
        json={"title": "Nope"},
        headers=employee_headers,
    )
    assert blocked_patch.status_code == 403

    blocked_delete = client.delete(
        f"/api/v1/company-documents/{doc_id}",
        headers=employee_headers,
    )
    assert blocked_delete.status_code == 403


def test_hr_can_edit_archive_and_delete_company_document(client, db_session):
    headers = auth_header(client)
    _use_storage(client, _mock_storage())
    category_id = _category_id(db_session)
    other_category = _category_id(db_session, "company_policies")
    created = _upload_company(client, headers, category_id=category_id)
    doc_id = created.json()["id"]

    updated = client.patch(
        f"/api/v1/company-documents/{doc_id}",
        json={
            "title": "Updated Handbook",
            "category_id": other_category,
            "status": "archived",
        },
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["title"] == "Updated Handbook"
    assert updated.json()["category_id"] == other_category
    assert updated.json()["status"] == "archived"

    deleted = client.delete(f"/api/v1/company-documents/{doc_id}", headers=headers)
    assert deleted.status_code == 204, deleted.text
    assert client.get("/api/v1/company-documents", headers=headers).json() == []


def test_employee_does_not_see_archived_company_documents(client, db_session):
    admin_headers = auth_header(client)
    _use_storage(client, _mock_storage())
    category_id = _category_id(db_session)
    created = _upload_company(client, admin_headers, category_id=category_id)
    doc_id = created.json()["id"]
    client.patch(
        f"/api/v1/company-documents/{doc_id}",
        json={"status": "archived"},
        headers=admin_headers,
    )

    _application, _job, employee_headers, _headers, _body = _hire(
        client, db_session, email="docs.archived.emp@test.com"
    )
    listed = client.get("/api/v1/company-documents", headers=employee_headers)
    assert listed.status_code == 200
    assert listed.json() == []

    missing = client.get(
        f"/api/v1/company-documents/{doc_id}/url",
        headers=employee_headers,
    )
    assert missing.status_code == 404


def test_categories_endpoint_returns_seeded_categories(client, db_session):
    headers = auth_header(client)
    response = client.get("/api/v1/company-documents/categories", headers=headers)
    assert response.status_code == 200, response.text
    labels = [item["label"] for item in response.json()]
    assert "HR Policies" in labels
    assert "Employee Handbook" in labels
    assert "Other" in labels
