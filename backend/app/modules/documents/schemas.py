from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.documents.models import CompanyDocumentStatus, DocumentType


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


class CompanyDocumentCategoryResponse(BaseModel):
    id: int
    slug: str
    label: str
    sort_order: int
    is_active: bool

    model_config = {"from_attributes": True}


class CompanyDocumentResponse(BaseModel):
    id: int
    title: str
    description: str | None
    category_id: int
    category_slug: str
    category_label: str
    original_filename: str
    content_type: str
    size_bytes: int
    version: int
    uploaded_by_user_id: int
    uploaded_by_name: str
    status: CompanyDocumentStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CompanyDocumentUpdateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    category_id: int | None = None
    status: CompanyDocumentStatus | None = None


class PrivateDocumentResponse(BaseModel):
    id: int
    owner_employee_id: int
    title: str
    description: str | None
    original_filename: str
    content_type: str
    size_bytes: int
    uploaded_by_user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PrivateDocumentUpdateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
