from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.modules.documents.models import (
    CompanyDocument,
    CompanyDocumentCategory,
    CompanyDocumentStatus,
    PrivateDocument,
)


class CompanyDocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_categories(self, *, active_only: bool = True) -> list[CompanyDocumentCategory]:
        query = self.db.query(CompanyDocumentCategory)
        if active_only:
            query = query.filter(CompanyDocumentCategory.is_active.is_(True))
        return query.order_by(
            CompanyDocumentCategory.sort_order.asc(),
            CompanyDocumentCategory.id.asc(),
        ).all()

    def get_category(self, category_id: int) -> CompanyDocumentCategory | None:
        return (
            self.db.query(CompanyDocumentCategory)
            .filter(CompanyDocumentCategory.id == category_id)
            .first()
        )

    def get_category_by_slug(self, slug: str) -> CompanyDocumentCategory | None:
        return (
            self.db.query(CompanyDocumentCategory)
            .filter(CompanyDocumentCategory.slug == slug)
            .first()
        )

    def list_documents(
        self,
        *,
        q: str | None = None,
        category_id: int | None = None,
        status: CompanyDocumentStatus | None = None,
    ) -> list[CompanyDocument]:
        query = self.db.query(CompanyDocument).options(
            joinedload(CompanyDocument.category),
            joinedload(CompanyDocument.uploaded_by),
        )
        if status is not None:
            query = query.filter(CompanyDocument.status == status)
        if category_id is not None:
            query = query.filter(CompanyDocument.category_id == category_id)
        if q:
            pattern = f"%{q.strip()}%"
            query = query.filter(
                or_(
                    CompanyDocument.title.ilike(pattern),
                    CompanyDocument.description.ilike(pattern),
                    CompanyDocument.original_filename.ilike(pattern),
                )
            )
        return query.order_by(CompanyDocument.updated_at.desc(), CompanyDocument.id.desc()).all()

    def get_by_id(self, document_id: int) -> CompanyDocument | None:
        return (
            self.db.query(CompanyDocument)
            .options(
                joinedload(CompanyDocument.category),
                joinedload(CompanyDocument.uploaded_by),
            )
            .filter(CompanyDocument.id == document_id)
            .first()
        )

    def add(self, document: CompanyDocument, *, commit: bool = True) -> CompanyDocument:
        self.db.add(document)
        self.db.flush()
        if commit:
            self.db.commit()
            self.db.refresh(document)
        return document

    def save(self, document: CompanyDocument) -> CompanyDocument:
        self.db.commit()
        self.db.refresh(document)
        return document

    def delete(self, document: CompanyDocument) -> None:
        self.db.delete(document)
        self.db.commit()

    def add_category(
        self, category: CompanyDocumentCategory, *, commit: bool = True
    ) -> CompanyDocumentCategory:
        self.db.add(category)
        self.db.flush()
        if commit:
            self.db.commit()
            self.db.refresh(category)
        return category


class PrivateDocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_for_owner(self, owner_employee_id: int) -> list[PrivateDocument]:
        return (
            self.db.query(PrivateDocument)
            .filter(PrivateDocument.owner_employee_id == owner_employee_id)
            .order_by(PrivateDocument.updated_at.desc(), PrivateDocument.id.desc())
            .all()
        )

    def get_for_owner(
        self, document_id: int, owner_employee_id: int
    ) -> PrivateDocument | None:
        return (
            self.db.query(PrivateDocument)
            .filter(
                PrivateDocument.id == document_id,
                PrivateDocument.owner_employee_id == owner_employee_id,
            )
            .first()
        )

    def add(self, document: PrivateDocument, *, commit: bool = True) -> PrivateDocument:
        self.db.add(document)
        self.db.flush()
        if commit:
            self.db.commit()
            self.db.refresh(document)
        return document

    def save(self, document: PrivateDocument) -> PrivateDocument:
        self.db.commit()
        self.db.refresh(document)
        return document

    def delete(self, document: PrivateDocument) -> None:
        self.db.delete(document)
        self.db.commit()
