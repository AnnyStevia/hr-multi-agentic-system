from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.documents.repository import DocumentRepository
from app.modules.documents.service import DocumentService
from app.modules.employees.repository import EmployeeRepository
from app.shared.storage import StorageService, get_storage_service


def get_document_service(
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> DocumentService:
    return DocumentService(
        DocumentRepository(db),
        EmployeeRepository(db),
        storage,
    )
