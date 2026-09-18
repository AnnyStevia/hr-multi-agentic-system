from pathlib import Path
import re

from app.shared.exceptions import AppException

MAX_PROFILE_PICTURE_BYTES = 2 * 1024 * 1024
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
JPEG_MIME = "image/jpeg"
PNG_MIME = "image/png"
GENERIC_MIMES = {"", "application/octet-stream", "binary/octet-stream"}

JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
EXECUTABLE_MAGIC = (b"MZ", b"\x7fELF")


class ValidatedProfilePicture:
    def __init__(self, filename: str, content_type: str, content: bytes, extension: str):
        self.filename = filename
        self.content_type = content_type
        self.content = content
        self.extension = extension


def validate_profile_picture(
    filename: str | None, declared_mime: str | None, content: bytes
) -> ValidatedProfilePicture:
    if not filename or not filename.strip():
        raise AppException("A picture filename is required", status_code=400)
    if not content:
        raise AppException("The uploaded picture is empty", status_code=400)
    if len(content) > MAX_PROFILE_PICTURE_BYTES:
        raise AppException("Profile picture exceeds the 2 MB size limit", status_code=413)
    if content.startswith(EXECUTABLE_MAGIC):
        raise AppException("Executable files are not allowed", status_code=400)

    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise AppException("Only JPG and PNG images are allowed", status_code=400)

    sniffed_mime = _sniff_mime(content, extension)
    declared = (declared_mime or "").split(";")[0].strip().lower()
    if declared and declared not in GENERIC_MIMES and declared != sniffed_mime:
        raise AppException("The file content does not match the declared type", status_code=400)

    return ValidatedProfilePicture(
        filename=sanitize_filename(filename),
        content_type=sniffed_mime,
        content=content,
        extension=extension,
    )


def sanitize_filename(filename: str) -> str:
    name = Path(filename).name.strip()
    name = re.sub(r"[^\w.\-() ]+", "_", name, flags=re.UNICODE)
    name = name.strip(" .") or "profile-picture"
    return name[:255]


def _sniff_mime(content: bytes, extension: str) -> str:
    if extension in {".jpg", ".jpeg"} and content.startswith(JPEG_MAGIC):
        return JPEG_MIME
    if extension == ".png" and content.startswith(PNG_MAGIC):
        return PNG_MIME
    raise AppException("The file content is not a valid JPG or PNG image", status_code=400)
