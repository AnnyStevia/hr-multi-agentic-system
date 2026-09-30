"""Unit tests: chat history sanitization and digests."""

from __future__ import annotations

from app.ai.history.sanitize import (
    derive_title,
    sanitize_citations_for_history,
    token_digest,
)


def test_sanitize_citations_keeps_safe_metadata_only():
    raw = [
        {
            "citation_id": 1,
            "document_name": "Handbook",
            "page_start": 2,
            "page_end": 3,
            "company_document_id": 9,
            "excerpt": "secret body text",
            "storage_key": "s3://bucket/key",
            "content_hash": "abc",
        },
        {
            "page_number": 4,
            "chunk_text": "should drop via forbidden substring in key",
            "document_name": "Other",
        },
        "not-a-dict",
    ]
    cleaned = sanitize_citations_for_history(raw)
    assert cleaned == [
        {
            "citation_id": 1,
            "document_name": "Handbook",
            "page_start": 2,
            "page_end": 3,
            "company_document_id": 9,
        },
        {"page_number": 4, "document_name": "Other"},
    ]


def test_sanitize_citations_empty():
    assert sanitize_citations_for_history(None) is None
    assert sanitize_citations_for_history([]) is None


def test_token_digest_is_sha256_hex():
    digest = token_digest("live-token-value")
    assert len(digest) == 64
    assert digest == token_digest("live-token-value")
    assert digest != token_digest("other")
    assert "live-token" not in digest


def test_derive_title_truncates():
    assert derive_title("short") == "short"
    long = "x" * 100
    title = derive_title(long, max_len=80)
    assert len(title) == 80
    assert title.endswith("…")
