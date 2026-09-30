"""Sanitize citation payloads before chat-history persistence."""

from __future__ import annotations

from typing import Any


_SAFE_CITATION_KEYS = frozenset(
    {
        "citation_id",
        "document_name",
        "page_start",
        "page_end",
        "company_document_id",
        "page_number",
    }
)

_FORBIDDEN_SUBSTRINGS = (
    "storage_key",
    "presigned",
    "s3://",
    "excerpt",
    "chunk",
    "content_hash",
    "embedding",
)


def sanitize_citations_for_history(
    citations: list[dict[str, Any]] | None,
) -> list[dict[str, Any]] | None:
    """Keep Knowledge-style metadata only; drop excerpts and unsafe keys."""
    if not citations:
        return None
    cleaned: list[dict[str, Any]] = []
    for raw in citations:
        if not isinstance(raw, dict):
            continue
        item: dict[str, Any] = {}
        for key, value in raw.items():
            lowered = str(key).lower()
            if any(bad in lowered for bad in _FORBIDDEN_SUBSTRINGS):
                continue
            if key not in _SAFE_CITATION_KEYS:
                continue
            if isinstance(value, str) and any(
                bad in value.lower() for bad in ("s3://", "presigned", "x-amz-")
            ):
                continue
            item[key] = value
        if item:
            cleaned.append(item)
    return cleaned or None


def token_digest(token: str) -> str:
    import hashlib

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def derive_title(message: str, *, max_len: int = 80) -> str:
    text = " ".join((message or "").strip().split())
    if not text:
        return "Conversation"
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"
