"""Authorized document file payload for AI/domain consumers (no storage keys)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuthorizedDocumentBytes:
    """File bytes after authorization — never includes storage_key or URLs."""

    document_id: int
    title: str | None
    filename: str
    content_type: str
    size_bytes: int
    file_bytes: bytes
