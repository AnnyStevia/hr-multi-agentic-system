"""Citation registry and marker validation for grounded answers."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.ai.rag.generation.schemas import Citation

_CITATION_MARKER_RE = re.compile(r"\[(\d+)\]")


@dataclass(frozen=True)
class CitationSource:
    citation_id: int
    chunk_id: int
    company_document_id: int
    page_start: int
    page_end: int
    document_name: str | None
    content_hash: str
    content: str


def build_registry(sources: list[CitationSource]) -> dict[int, CitationSource]:
    return {source.citation_id: source for source in sources}


def extract_citation_ids(answer: str) -> list[int]:
    """Return citation IDs in first-appearance order (deduped)."""
    seen: set[int] = set()
    ordered: list[int] = []
    for match in _CITATION_MARKER_RE.finditer(answer or ""):
        citation_id = int(match.group(1))
        if citation_id in seen:
            continue
        seen.add(citation_id)
        ordered.append(citation_id)
    return ordered


def sanitize_answer_and_citations(
    answer: str,
    registry: dict[int, CitationSource],
) -> tuple[str, list[Citation]]:
    """Drop invalid [n] markers; build Citation list from registry only."""
    valid_ids = set(registry.keys())
    referenced = extract_citation_ids(answer)

    def _replace(match: re.Match[str]) -> str:
        citation_id = int(match.group(1))
        if citation_id in valid_ids:
            return match.group(0)
        return ""

    cleaned = _CITATION_MARKER_RE.sub(_replace, answer or "")
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r" {2,}", " ", cleaned).strip()

    citations: list[Citation] = []
    for citation_id in referenced:
        source = registry.get(citation_id)
        if source is None:
            continue
        citations.append(
            Citation(
                citation_id=source.citation_id,
                chunk_id=source.chunk_id,
                company_document_id=source.company_document_id,
                page_start=source.page_start,
                page_end=source.page_end,
                document_name=source.document_name,
                content_hash=source.content_hash,
            )
        )
    return cleaned, citations
