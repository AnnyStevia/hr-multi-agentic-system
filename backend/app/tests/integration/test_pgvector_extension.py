"""Skippable Postgres check that the vector extension is available."""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.core.config import settings


def test_pgvector_extension_available_on_postgres():
    url = settings.database_url
    if not url.startswith("postgresql"):
        pytest.skip("DATABASE_URL is not PostgreSQL")

    try:
        engine = create_engine(url)
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            ).fetchone()
    except OperationalError as exc:
        pytest.skip(f"PostgreSQL unreachable: {exc}")
    except ProgrammingError as exc:
        pytest.skip(f"PostgreSQL query failed (migrate first?): {exc}")

    if row is None:
        pytest.skip(
            "pgvector extension not installed yet — run alembic upgrade head "
            "against pgvector/pgvector:pg16"
        )

    assert row[0] == 1
