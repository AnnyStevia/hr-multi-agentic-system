"""Thin smoke wrapper for live RAG evaluation (opt-in Gemini).

  $env:PYTHONPATH = "."
  .\\.venv\\Scripts\\python.exe scripts/smoke_rag_evaluation.py
"""

from app.ai.evaluation.runner import main

if __name__ == "__main__":
    raise SystemExit(main(["--live-generation"]))
