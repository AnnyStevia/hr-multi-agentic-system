from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.documents.models import DocumentType


class DocumentResponse(BaseModel):
    id: int
    employee_id: int
    document_type: DocumentType
    original_filename: str
    content_type: str
    size_bytes: int
    uploaded_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PresignedDocumentUrlResponse(BaseModel):
    url: str
    filename: str
    content_type: str
    expires_in: int
    download: bool


class DocumentTypeForm(BaseModel):
    document_type: DocumentType = Field(...)
