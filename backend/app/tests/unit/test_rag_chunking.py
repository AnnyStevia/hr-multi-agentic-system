"""Unit tests for deterministic RAG chunking and provenance (no Gemini / no DB)."""

from app.ai.rag.chunking import DocumentChunker, sha256_hex
from app.ai.rag.chunking.chunker import pages_to_ingestion_result
from app.ai.rag.ingestion.schemas import IngestedPage


def _words(n: int, prefix: str = "w") -> str:
    return " ".join(f"{prefix}{i}" for i in range(n))


def test_short_one_page_document_one_chunk():
    result = pages_to_ingestion_result(
        [IngestedPage(page_number=1, text="Hello company handbook.")],
        company_document_id=7,
    )
    chunks = DocumentChunker(chunk_size=800, overlap=100).chunk(
        result, document_version=1
    )
    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].page_start == 1
    assert chunks[0].page_end == 1
    assert "Hello company handbook." in chunks[0].content


def test_long_document_multiple_chunks():
    text = _words(250)
    result = pages_to_ingestion_result(
        [IngestedPage(page_number=1, text=text)],
        company_document_id=1,
    )
    chunks = DocumentChunker(chunk_size=100, overlap=20).chunk(
        result, document_version=1
    )
    assert len(chunks) >= 3
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    for chunk in chunks:
        assert len(chunk.content.split()) <= 100
        assert chunk.content.strip()


def test_overlap_is_deterministic():
    text = _words(180)
    result = pages_to_ingestion_result(
        [IngestedPage(page_number=1, text=text)],
        company_document_id=1,
    )
    chunker = DocumentChunker(chunk_size=100, overlap=20)
    first = chunker.chunk(result, document_version=2)
    second = chunker.chunk(result, document_version=2)
    assert [c.content for c in first] == [c.content for c in second]
    assert [c.content_hash for c in first] == [c.content_hash for c in second]
    # Adjacent chunks share trailing/leading overlap words when hard-split.
    if len(first) >= 2:
        a_words = first[0].content.split()
        b_words = first[1].content.split()
        assert a_words[-20:] == b_words[:20]


def test_page_boundaries_preserved():
    result = pages_to_ingestion_result(
        [
            IngestedPage(page_number=1, text=_words(40, "a")),
            IngestedPage(page_number=2, text=_words(40, "b")),
        ],
        company_document_id=3,
    )
    chunks = DocumentChunker(chunk_size=800, overlap=100).chunk(
        result, document_version=1
    )
    assert len(chunks) == 2
    assert chunks[0].page_start == 1 and chunks[0].page_end == 1
    assert chunks[1].page_start == 2 and chunks[1].page_end == 2
    assert chunks[0].content.split()[0].startswith("a")
    assert chunks[1].content.split()[0].startswith("b")


def test_chunk_ordering_stable():
    result = pages_to_ingestion_result(
        [
            IngestedPage(page_number=1, text=_words(120, "p1")),
            IngestedPage(page_number=2, text=_words(120, "p2")),
        ],
        company_document_id=9,
    )
    chunks = DocumentChunker(chunk_size=50, overlap=10).chunk(
        result, document_version=1
    )
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert chunks == DocumentChunker(chunk_size=50, overlap=10).chunk(
        result, document_version=1
    )


def test_very_long_paragraph_is_split_safely():
    huge = _words(350)
    result = pages_to_ingestion_result(
        [IngestedPage(page_number=1, text=huge)],
        company_document_id=1,
    )
    chunks = DocumentChunker(chunk_size=100, overlap=10).chunk(
        result, document_version=1
    )
    assert len(chunks) >= 4
    for chunk in chunks:
        assert 0 < len(chunk.content.split()) <= 100


def test_empty_pages_do_not_produce_empty_chunks():
    result = pages_to_ingestion_result(
        [
            IngestedPage(page_number=1, text=""),
            IngestedPage(page_number=2, text="   \n\t  "),
            IngestedPage(page_number=3, text="Only real content here."),
        ],
        company_document_id=1,
    )
    chunks = DocumentChunker(chunk_size=800, overlap=100).chunk(
        result, document_version=1
    )
    assert len(chunks) == 1
    assert chunks[0].page_start == 3
    assert chunks[0].content.strip()
    assert all(c.content.strip() for c in chunks)


def test_empty_document_handled():
    result = pages_to_ingestion_result([], company_document_id=1)
    chunks = DocumentChunker(chunk_size=800, overlap=100).chunk(
        result, document_version=1
    )
    assert chunks == []

    blank = pages_to_ingestion_result(
        [IngestedPage(page_number=1, text=""), IngestedPage(page_number=2, text="  ")],
        company_document_id=1,
    )
    assert DocumentChunker(chunk_size=50, overlap=5).chunk(blank, document_version=1) == []


def test_provenance_fields_and_stable_hash():
    result = pages_to_ingestion_result(
        [IngestedPage(page_number=1, text="Policy section one.")],
        company_document_id=42,
    )
    chunks = DocumentChunker(chunk_size=800, overlap=100).chunk(
        result, document_version=3
    )
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.metadata == {
        "company_document_id": 42,
        "page_start": 1,
        "page_end": 1,
        "chunk_index": 0,
        "document_version": 3,
        "content_hash": chunk.content_hash,
    }
    assert chunk.content_hash == sha256_hex(chunk.content)
    assert chunk.content_hash == sha256_hex(chunk.content)
    again = DocumentChunker(chunk_size=800, overlap=100).chunk(
        result, document_version=3
    )
    assert again[0].content_hash == chunk.content_hash
    assert again[0].metadata == chunk.metadata


def test_paragraph_boundaries_within_page():
    page = "First paragraph here.\n\nSecond paragraph there."
    result = pages_to_ingestion_result(
        [IngestedPage(page_number=1, text=page)],
        company_document_id=1,
    )
    chunks = DocumentChunker(chunk_size=800, overlap=100).chunk(
        result, document_version=1
    )
    assert len(chunks) == 1
    assert "First paragraph here." in chunks[0].content
    assert "Second paragraph there." in chunks[0].content
