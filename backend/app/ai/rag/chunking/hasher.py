"""SHA-256 helpers for RAG chunk content hashing."""

from __future__ import annotations

import hashlib


def sha256_hex(text: str) -> str:
    """Return the hex SHA-256 digest of UTF-8-encoded ``text``."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
