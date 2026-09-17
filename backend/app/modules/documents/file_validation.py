from pathlib import Path
import re

from app.shared.exceptions import AppException

MAX_DOCUMENT_BYTES = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png"}
PDF_MIME = "application/pdf"
DOC_MIME = "application/msword"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
JPEG_MIME = "image/jpeg"
PNG_MIME = "image/png"
GENERIC_MIMES = {"", "application/octet-stream", "binary/octet-stream"}

PDF_MAGIC = b"%PDF"
OLE_MAGIC = b"\xd0\xcf\x11\xe0"
ZIP_MAGIC = b"PK"
JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
EXECUTABLE_MAGIC = (b"MZ", b"\x7fELF")


class ValidatedUpload:
    def __init__(self, filename: str, content_type: str, content: bytes, extension: str):
        self.filename = filename
        self.content_type = content_type
        self.content = content
        self.extension = extension


def validate_employee_document(
    filename: str | None, declared_mime: str | None, content: bytes
) -> ValidatedUpload:
    if not filename or not filename.strip():
        raise AppException("A document filename is required", status_code=400)
    if not content:
        raise AppException("The uploaded document is empty", status_code=400)
    if len(content) > MAX_DOCUMENT_BYTES:
        raise AppException("Document exceeds the 5 MB size limit", status_code=413)
    if content.startswith(EXECUTABLE_MAGIC):
        raise AppException("Executable files are not allowed", status_code=400)

    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise AppException(
            "Only PDF, DOC, DOCX, JPG, and PNG documents are allowed",
            status_code=400,
        )

    sniffed_mime = _sniff_mime(content, extension)
    declared = (declared_mime or "").split(";")[0].strip().lower()
    if declared and declared not in GENERIC_MIMES and declared != sniffed_mime:
        raise AppException("The file content does not match the declared type", status_code=400)

    safe_name = sanitize_filename(filename)
    return ValidatedUpload(
        filename=safe_name,
        content_type=sniffed_mime,
        content=content,
        extension=extension,
    )


def sanitize_filename(filename: str) -> str:
    name = Path(filename).name.strip()
    name = re.sub(r"[^\w.\-() ]+", "_", name, flags=re.UNICODE)
    name = name.strip(" .") or "document"
    return name[:255]


def _sniff_mime(content: bytes, extension: str) -> str:
    if extension == ".pdf" and content.startswith(PDF_MAGIC):
        return PDF_MIME
    if extension == ".doc" and content.startswith(OLE_MAGIC):
        return DOC_MIME
    if extension == ".docx" and content.startswith(ZIP_MAGIC):
        return DOCX_MIME
    if extension in {".jpg", ".jpeg"} and content.startswith(JPEG_MAGIC):
        return JPEG_MIME
    if extension == ".png" and content.startswith(PNG_MAGIC):
        return PNG_MIME
    raise AppException(
        "The file content is not a valid PDF, DOC, DOCX, JPG, or PNG document",
        status_code=400,
    )
