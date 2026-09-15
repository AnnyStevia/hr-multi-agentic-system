from unittest.mock import MagicMock

from app.shared.storage import StorageException


def test_s3_health_connected(client, monkeypatch):
    storage = MagicMock()
    monkeypatch.setattr("app.main.get_storage_service", lambda: storage)
    monkeypatch.setattr("app.main.settings.app_env", "development")
    monkeypatch.setattr("app.main.settings.aws_s3_bucket_name", "hr-platform-documents-pfe")
    monkeypatch.setattr("app.main.settings.aws_region", "eu-north-1")

    response = client.get("/health/s3")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["storage"] == "connected"
    assert data["bucket"] == "hr-platform-documents-pfe"
    assert data["region"] == "eu-north-1"
    assert "aws_secret_access_key" not in str(data).lower()
    assert "access_key" not in str(data).lower()
    storage.check_connectivity.assert_called_once()


def test_s3_health_unhealthy_when_storage_fails(client, monkeypatch):
    storage = MagicMock()
    storage.check_connectivity.side_effect = StorageException(
        "Cannot reach object storage: AccessDenied",
        status_code=502,
    )
    monkeypatch.setattr("app.main.get_storage_service", lambda: storage)
    monkeypatch.setattr("app.main.settings.app_env", "development")

    response = client.get("/health/s3")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unhealthy"
    assert "Cannot reach object storage" in data["storage"]


def test_s3_health_hidden_outside_development(client, monkeypatch):
    storage = MagicMock()
    monkeypatch.setattr("app.main.get_storage_service", lambda: storage)
    monkeypatch.setattr("app.main.settings.app_env", "production")

    response = client.get("/health/s3")

    assert response.status_code == 404
    storage.check_connectivity.assert_not_called()
