from app.modules.recruitment.file_validation import MAX_DOCUMENT_BYTES, validate_application_document
from app.shared.exceptions import AppException

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
DOC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 20
DOCX = b"PK\x03\x04" + b"\x00" * 20


def test_accepts_pdf_doc_and_docx():
    pdf = validate_application_document("cv.pdf", "application/pdf", PDF)
    assert pdf.content_type == "application/pdf"
    doc = validate_application_document("cv.doc", "application/msword", DOC)
    assert doc.extension == ".doc"
    docx = validate_application_document(
        "cv.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        DOCX,
    )
    assert docx.extension == ".docx"


def test_rejects_mismatched_extension_and_content():
    try:
        validate_application_document("cv.pdf", "application/pdf", DOCX)
        raise AssertionError("Expected invalid PDF content to fail")
    except AppException as exc:
        assert exc.status_code == 400


def test_rejects_executable_and_unknown_types():
    try:
        validate_application_document("malware.exe", "application/octet-stream", b"MZ\x90\x00")
        raise AssertionError("Expected executable to fail")
    except AppException as exc:
        assert exc.status_code == 400

    try:
        validate_application_document("notes.txt", "text/plain", b"hello")
        raise AssertionError("Expected text file to fail")
    except AppException as exc:
        assert exc.status_code == 400


def test_rejects_oversized_file():
    payload = PDF + (b"0" * (MAX_DOCUMENT_BYTES + 1))
    try:
        validate_application_document("cv.pdf", "application/pdf", payload)
        raise AssertionError("Expected oversized file to fail")
    except AppException as exc:
        assert exc.status_code == 413
