import pytest

from app.tests.integration.test_application_review import _hr_headers, _submit_application


@pytest.mark.parametrize(
    "current,target",
    [
        ("submitted", "screening"),
        ("submitted", "rejected"),
        ("screening", "shortlisted"),
        ("screening", "rejected"),
    ],
)
def test_api_allows_valid_status_transitions(client, db_session, current, target):
    application, _job, _candidate_headers, _storage = _submit_application(client, db_session)
    headers = _hr_headers(client, db_session)
    if current != "submitted":
        moved = client.patch(
            f"/api/v1/applications/{application['id']}/status",
            json={"status": current},
            headers=headers,
        )
        assert moved.status_code == 200, moved.text

    response = client.patch(
        f"/api/v1/applications/{application['id']}/status",
        json={"status": target},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == target


@pytest.mark.parametrize(
    "setup,target",
    [
        ("submitted", "shortlisted"),
        ("screening", "submitted"),
        ("shortlisted", "submitted"),
        ("shortlisted", "screening"),
        ("shortlisted", "rejected"),
        ("rejected", "screening"),
        ("rejected", "shortlisted"),
        ("rejected", "submitted"),
    ],
)
def test_api_rejects_invalid_status_transitions(client, db_session, setup, target):
    application, _job, _candidate_headers, _storage = _submit_application(client, db_session)
    headers = _hr_headers(client, db_session)
    application_id = application["id"]

    if setup == "screening":
        assert client.patch(
            f"/api/v1/applications/{application_id}/status",
            json={"status": "screening"},
            headers=headers,
        ).status_code == 200
    elif setup == "shortlisted":
        assert client.patch(
            f"/api/v1/applications/{application_id}/status",
            json={"status": "screening"},
            headers=headers,
        ).status_code == 200
        assert client.patch(
            f"/api/v1/applications/{application_id}/status",
            json={"status": "shortlisted"},
            headers=headers,
        ).status_code == 200
    elif setup == "rejected":
        assert client.patch(
            f"/api/v1/applications/{application_id}/status",
            json={"status": "rejected"},
            headers=headers,
        ).status_code == 200

    response = client.patch(
        f"/api/v1/applications/{application_id}/status",
        json={"status": target},
        headers=headers,
    )
    assert response.status_code == 400
    detail = client.get(f"/api/v1/applications/{application_id}", headers=headers)
    assert detail.json()["status"] == setup
