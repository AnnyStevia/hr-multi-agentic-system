from io import BytesIO
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from app.core.config import Settings
from app.shared.storage import S3StorageService, StorageException


BUCKET = "hr-platform-documents-pfe"
REGION = "eu-north-1"


def _client_error(code: str, operation: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}}, operation)


def _service(client: MagicMock | None = None) -> S3StorageService:
    return S3StorageService(client=client or MagicMock(), bucket_name=BUCKET, region=REGION)


def test_upload_file_puts_object_on_private_bucket():
    client = MagicMock()
    payload = BytesIO(b"ok")
    stored = _service(client).upload_file(
        "healthchecks/ping.txt",
        payload,
        content_type="text/plain",
    )

    client.put_object.assert_called_once()
    kwargs = client.put_object.call_args.kwargs
    assert kwargs["Bucket"] == BUCKET
    assert kwargs["Key"] == "healthchecks/ping.txt"
    assert kwargs["Body"] is payload
    assert kwargs["ContentType"] == "text/plain"
    assert "ACL" not in kwargs
    assert stored.key == "healthchecks/ping.txt"
    assert stored.bucket == BUCKET
    assert stored.content_type == "text/plain"
    assert not hasattr(stored, "aws_secret_access_key")


def test_upload_file_wraps_s3_errors():
    client = MagicMock()
    client.put_object.side_effect = _client_error("AccessDenied", "PutObject")

    with pytest.raises(StorageException) as exc:
        _service(client).upload_file("docs/cv.pdf", BytesIO(b"pdf"))

    assert exc.value.status_code == 502
    assert "AccessDenied" in exc.value.message
    assert "SECRET" not in exc.value.message


def test_delete_file_removes_object():
    client = MagicMock()
    _service(client).delete_file("docs/cv.pdf")
    client.delete_object.assert_called_once_with(Bucket=BUCKET, Key="docs/cv.pdf")


def test_delete_file_wraps_s3_errors():
    client = MagicMock()
    client.delete_object.side_effect = _client_error("InternalError", "DeleteObject")

    with pytest.raises(StorageException) as exc:
        _service(client).delete_file("docs/cv.pdf")

    assert exc.value.status_code == 502
    assert "InternalError" in exc.value.message


def test_generate_presigned_url_returns_temporary_get_url():
    client = MagicMock()
    client.generate_presigned_url.return_value = (
        "https://example.s3.amazonaws.com/docs/cv.pdf?X-Amz-Algorithm=AWS4-HMAC-SHA256"
    )

    url = _service(client).generate_presigned_url("docs/cv.pdf", expires_in=120)

    client.generate_presigned_url.assert_called_once_with(
        ClientMethod="get_object",
        Params={"Bucket": BUCKET, "Key": "docs/cv.pdf"},
        ExpiresIn=120,
    )
    assert url.startswith("https://")
    assert "aws_secret_access_key" not in url.lower()


def test_generate_presigned_url_can_force_inline_view():
    client = MagicMock()
    client.generate_presigned_url.return_value = "https://example.s3.amazonaws.com/docs/cv.pdf"

    _service(client).generate_presigned_url(
        "docs/cv.pdf",
        expires_in=120,
        filename="cv.pdf",
        download=False,
    )

    params = client.generate_presigned_url.call_args.kwargs["Params"]
    assert params["ResponseContentDisposition"] == 'inline; filename="cv.pdf"'


def test_generate_presigned_url_wraps_s3_errors():
    client = MagicMock()
    client.generate_presigned_url.side_effect = _client_error("AccessDenied", "GeneratePresignedUrl")

    with pytest.raises(StorageException) as exc:
        _service(client).generate_presigned_url("docs/cv.pdf")

    assert exc.value.status_code == 502


def test_generate_presigned_url_rejects_invalid_expiry():
    with pytest.raises(StorageException) as exc:
        _service().generate_presigned_url("docs/cv.pdf", expires_in=0)
    assert exc.value.status_code == 400


def test_empty_object_key_is_rejected():
    with pytest.raises(StorageException) as exc:
        _service().delete_file("   ")
    assert exc.value.status_code == 400


def test_get_file_metadata_maps_head_object():
    client = MagicMock()
    client.head_object.return_value = {"ContentType": "application/pdf", "ContentLength": 12}

    metadata = _service(client).get_file_metadata("docs/cv.pdf")

    client.head_object.assert_called_once_with(Bucket=BUCKET, Key="docs/cv.pdf")
    assert metadata.content_type == "application/pdf"
    assert metadata.content_length == 12


def test_get_file_metadata_not_found():
    client = MagicMock()
    client.head_object.side_effect = _client_error("404", "HeadObject")

    with pytest.raises(StorageException) as exc:
        _service(client).get_file_metadata("missing.pdf")

    assert exc.value.status_code == 404


def test_download_file_reads_object_body():
    client = MagicMock()
    body = MagicMock()
    body.read.return_value = b"%PDF-1.4"
    client.get_object.return_value = {"Body": body}

    data = _service(client).download_file("docs/cv.pdf")

    client.get_object.assert_called_once_with(Bucket=BUCKET, Key="docs/cv.pdf")
    assert data == b"%PDF-1.4"


def test_download_file_not_found():
    client = MagicMock()
    client.get_object.side_effect = _client_error("NoSuchKey", "GetObject")

    with pytest.raises(StorageException) as exc:
        _service(client).download_file("missing.pdf")

    assert exc.value.status_code == 404


def test_check_connectivity_lists_bucket():
    client = MagicMock()
    _service(client).check_connectivity()
    client.list_objects_v2.assert_called_once_with(Bucket=BUCKET, MaxKeys=1)


def test_check_connectivity_wraps_s3_errors():
    client = MagicMock()
    client.list_objects_v2.side_effect = _client_error("AccessDenied", "ListObjectsV2")

    with pytest.raises(StorageException) as exc:
        _service(client).check_connectivity()

    assert exc.value.status_code == 502
    assert "Cannot reach object storage" in exc.value.message


def test_from_settings_requires_credentials(monkeypatch):
    monkeypatch.setattr("app.shared.storage.s3.boto3.client", MagicMock())
    settings = Settings(
        aws_access_key_id="",
        aws_secret_access_key="",
        aws_region=REGION,
        aws_s3_bucket_name=BUCKET,
    )

    with pytest.raises(StorageException) as exc:
        S3StorageService.from_settings(settings)

    assert exc.value.status_code == 503


def test_from_settings_builds_client_without_exposing_secret(monkeypatch):
    factory = MagicMock()
    monkeypatch.setattr("app.shared.storage.s3.boto3.client", factory)
    settings = Settings(
        aws_access_key_id="AKIAEXAMPLE",
        aws_secret_access_key="super-secret-value",
        aws_region=REGION,
        aws_s3_bucket_name=BUCKET,
    )

    service = S3StorageService.from_settings(settings)

    factory.assert_called_once_with(
        "s3",
        region_name=REGION,
        aws_access_key_id="AKIAEXAMPLE",
        aws_secret_access_key="super-secret-value",
    )
    assert not hasattr(service, "aws_secret_access_key")
    assert "super-secret-value" not in vars(service).values()
