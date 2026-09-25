"""Add fit assessment columns to applications (Phase 6.2).

Revision ID: 040_application_fit_assessment
Revises: 039_employee_employment_type
Create Date: 2026-09-25

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "040_application_fit_assessment"
down_revision = "039_employee_employment_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.add_column("applications", sa.Column("fit_score", sa.Integer(), nullable=True))
    op.add_column("applications", sa.Column("fit_level", sa.String(length=20), nullable=True))
    op.add_column("applications", sa.Column("fit_explanation", sa.Text(), nullable=True))
    op.add_column(
        "applications",
        sa.Column("matching_skills", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("missing_skills", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("applications", sa.Column("experience_match", sa.Text(), nullable=True))
    op.add_column("applications", sa.Column("education_match", sa.Text(), nullable=True))
    op.add_column(
        "applications",
        sa.Column("fit_analysis_version", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("fit_analyzed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.drop_column("applications", "fit_analyzed_at")
    op.drop_column("applications", "fit_analysis_version")
    op.drop_column("applications", "education_match")
    op.drop_column("applications", "experience_match")
    op.drop_column("applications", "missing_skills")
    op.drop_column("applications", "matching_skills")
    op.drop_column("applications", "fit_explanation")
    op.drop_column("applications", "fit_level")
    op.drop_column("applications", "fit_score")
