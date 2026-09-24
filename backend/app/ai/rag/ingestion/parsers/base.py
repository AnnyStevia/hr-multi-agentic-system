"""Provider-agnostic document parser contract."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.ai.rag.ingestion.schemas import IngestedPage


class DocumentParser(ABC):
    """Parse raw file bytes into page-aware text."""

    @abstractmethod
    def supports(self, content_type: str | None, filename: str | None) -> bool:
        raise NotImplementedError

    @abstractmethod
    def parse(self, file_bytes: bytes) -> list[IngestedPage]:
        raise NotImplementedError
