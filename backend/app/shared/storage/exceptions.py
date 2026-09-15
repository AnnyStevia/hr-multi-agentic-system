from app.shared.exceptions import AppException


class StorageException(AppException):
    """Raised when object storage cannot complete a request."""
