from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import BinaryIO


@dataclass(frozen=True)
class StoredObject:
    key: str
    bucket: str
    content_type: str | None = None


@dataclass(frozen=True)
class StoredObjectMetadata:
    key: str
    bucket: str
    content_type: str | None
    content_length: int | None


class StorageService(ABC):
    """Reusable object-storage contract for business services."""

    @abstractmethod
    def upload_file(
        self,
        key: str,
        data: BinaryIO,
        content_type: str | None = None,
    ) -> StoredObject:
        raise NotImplementedError

    @abstractmethod
    def delete_file(self, key: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def generate_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
        *,
        filename: str | None = None,
        download: bool = False,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_file_metadata(self, key: str) -> StoredObjectMetadata:
        raise NotImplementedError

    @abstractmethod
    def download_file(self, key: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def check_connectivity(self) -> None:
        raise NotImplementedError
