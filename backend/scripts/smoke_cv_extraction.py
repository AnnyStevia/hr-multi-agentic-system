"""Smoke: live CV extraction (1 Gemini structured call). Not part of default pytest.

Run from backend/ with a readable PDF path:

  $env:PYTHONPATH = "."
  $env:CV_SMOKE_PDF = "path\\to\\cv.pdf"
  .\\.venv\\Scripts\\python.exe scripts/smoke_cv_extraction.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from app.ai.agents.recruitment import CvExtractionService


def main() -> int:
    pdf_path = os.environ.get("CV_SMOKE_PDF")
    if not pdf_path:
        print("Set CV_SMOKE_PDF to a local PDF path.", file=sys.stderr)
        return 2
    path = Path(pdf_path)
    if not path.is_file():
        print(f"File not found: {path}", file=sys.stderr)
        return 2

    content = path.read_bytes()
    service = CvExtractionService()
    result = service.extract_from_upload(
        filename=path.name,
        content_type="application/pdf",
        content=content,
    )
    print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
