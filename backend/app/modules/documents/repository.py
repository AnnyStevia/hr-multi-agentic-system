from sqlalchemy.orm import Session

from app.modules.documents.models import Document, DocumentType


class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_employee_id(self, employee_id: int) -> list[Document]:
        return (
            self.db.query(Document)
            .filter(Document.employee_id == employee_id)
            .order_by(Document.uploaded_at.desc(), Document.id.desc())
            .all()
        )

    def get_by_id(self, document_id: int) -> Document | None:
        return self.db.query(Document).filter(Document.id == document_id).first()

    def get_for_employee(self, document_id: int, employee_id: int) -> Document | None:
        return (
            self.db.query(Document)
            .filter(Document.id == document_id, Document.employee_id == employee_id)
            .first()
        )

    def add(self, document: Document, *, commit: bool = True) -> Document:
        self.db.add(document)
        self.db.flush()
        if commit:
            self.db.commit()
            self.db.refresh(document)
        return document

    def save(self, document: Document) -> Document:
        self.db.commit()
        self.db.refresh(document)
        return document

    def delete(self, document: Document) -> None:
        self.db.delete(document)
        self.db.commit()

    def exists_for_employee(self, employee_id: int, document_type: DocumentType) -> bool:
        return (
            self.db.query(Document.id)
            .filter(
                Document.employee_id == employee_id,
                Document.document_type == document_type,
            )
            .first()
            is not None
        )
