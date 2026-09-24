from typing import BinaryIO

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import Settings
from app.shared.storage.base import StoredObject, StoredObjectMetadata, StorageService
from app.shared.storage.exceptions import StorageException


class S3StorageService(StorageService):
    """Private S3 implementation of StorageService. Credentials stay in the AWS client."""

    def __init__(self, client, bucket_name: str, region: str):
        if not bucket_name.strip():
            raise StorageException("Object storage bucket is not configured", status_code=503)
        self._client = client
        self._bucket_name = bucket_name
        self._region = region

    @classmethod
    def from_settings(cls, settings: Settings) -> "S3StorageService":
        if not settings.aws_access_key_id or not settings.aws_secret_access_key:
            raise StorageException("Object storage is not configured", status_code=503)
        if not settings.aws_s3_bucket_name.strip():
            raise StorageException("Object storage bucket is not configured", status_code=503)

        client = boto3.client(
            "s3",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )
        return cls(
            client=client,
            bucket_name=settings.aws_s3_bucket_name,
            region=settings.aws_region,
        )

    def upload_file(
        self,
        key: str,
        data: BinaryIO,
        content_type: str | None = None,
    ) -> StoredObject:
        object_key = _require_key(key)
        extra: dict[str, str] = {}
        if content_type:
            extra["ContentType"] = content_type

        try:
            self._client.put_object(
                Bucket=self._bucket_name,
                Key=object_key,
                Body=data,
                **extra,
            )
        except (ClientError, BotoCoreError) as exc:
            raise _storage_error(exc, "Failed to upload object") from exc

        return StoredObject(
            key=object_key,
            bucket=self._bucket_name,
            content_type=content_type,
        )

    def delete_file(self, key: str) -> None:
        object_key = _require_key(key)
        try:
            self._client.delete_object(Bucket=self._bucket_name, Key=object_key)
        except (ClientError, BotoCoreError) as exc:
            raise _storage_error(exc, "Failed to delete object") from exc

    def generate_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
        *,
        filename: str | None = None,
        download: bool = False,
    ) -> str:
        object_key = _require_key(key)
        if expires_in <= 0:
            raise StorageException("Presigned URL expiry must be greater than zero", status_code=400)

        params: dict[str, str] = {"Bucket": self._bucket_name, "Key": object_key}
        if filename:
            safe_name = filename.replace('"', "").replace("\r", "").replace("\n", "")
            disposition = "attachment" if download else "inline"
            params["ResponseContentDisposition"] = f'{disposition}; filename="{safe_name}"'

        try:
            url = self._client.generate_presigned_url(
                ClientMethod="get_object",
                Params=params,
                ExpiresIn=expires_in,
            )
        except (ClientError, BotoCoreError) as exc:
            raise _storage_error(exc, "Failed to generate download URL") from exc

        if not isinstance(url, str) or not url:
            raise StorageException("Failed to generate download URL", status_code=502)
        return url

    def get_file_metadata(self, key: str) -> StoredObjectMetadata:
        object_key = _require_key(key)
        try:
            response = self._client.head_object(Bucket=self._bucket_name, Key=object_key)
        except ClientError as exc:
            error_code = _client_error_code(exc)
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                raise StorageException("Object not found", status_code=404) from exc
            raise _storage_error(exc, "Failed to read object metadata") from exc
        except BotoCoreError as exc:
            raise _storage_error(exc, "Failed to read object metadata") from exc

        return StoredObjectMetadata(
            key=object_key,
            bucket=self._bucket_name,
            content_type=response.get("ContentType"),
            content_length=response.get("ContentLength"),
        )

    def download_file(self, key: str) -> bytes:
        object_key = _require_key(key)
        try:
            response = self._client.get_object(Bucket=self._bucket_name, Key=object_key)
            body = response["Body"].read()
        except ClientError as exc:
            error_code = _client_error_code(exc)
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                raise StorageException("Object not found", status_code=404) from exc
            raise _storage_error(exc, "Failed to download object") from exc
        except BotoCoreError as exc:
            raise _storage_error(exc, "Failed to download object") from exc
        if not isinstance(body, (bytes, bytearray)):
            raise StorageException("Failed to download object", status_code=502)
        return bytes(body)

    def check_connectivity(self) -> None:
        try:
            self._client.list_objects_v2(Bucket=self._bucket_name, MaxKeys=1)
        except (ClientError, BotoCoreError) as exc:
            raise _storage_error(exc, "Cannot reach object storage") from exc


def get_storage_service() -> StorageService:
    from app.core.config import settings

    return S3StorageService.from_settings(settings)


def _require_key(key: str) -> str:
    object_key = key.strip()
    if not object_key:
        raise StorageException("Object key is required", status_code=400)
    return object_key


def _client_error_code(exc: ClientError) -> str:
    error = exc.response.get("Error") if isinstance(exc.response, dict) else None
    if isinstance(error, dict):
        return str(error.get("Code", ""))
    return ""


def _storage_error(exc: Exception, message: str) -> StorageException:
    error_code = _client_error_code(exc) if isinstance(exc, ClientError) else ""
    detail = f"{message}: {error_code}" if error_code else message
    return StorageException(detail, status_code=502)
