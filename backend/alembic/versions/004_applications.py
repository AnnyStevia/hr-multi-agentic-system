"""Applications, job questions, and document metadata

Revision ID: 004_applications
Revises: 003_candidate_profile
Create Date: 2026-08-19

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "004_applications"
down_revision = "003_candidate_profile"
branch_labels = None
depends_on = None

question_type = postgresql.ENUM(
    "short_text",
    "long_text",
    "number",
    "yes_no",
    name="question_type",
    create_type=False,
)
application_status = postgresql.ENUM(
    "submitted",
    "shortlisted",
    "rejected",
    "interview",
    "hired",
    name="application_status",
    create_type=False,
)
document_kind = postgresql.ENUM("cv", "cover_letter", name="document_kind", create_type=False)


def _ensure_enum(type_name: str, values: tuple[str, ...]) -> None:
    quoted = ", ".join(f"'{value}'" for value in values)
    op.execute(
        sa.text(
            f"""
            DO $$ BEGIN
                CREATE TYPE {type_name} AS ENUM ({quoted});
            EXCEPTION
                WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
    )


def upgrade() -> None:
    _ensure_enum("question_type", ("short_text", "long_text", "number", "yes_no"))
    _ensure_enum(
        "application_status",
        ("submitted", "shortlisted", "rejected", "interview", "hired"),
    )
    _ensure_enum("document_kind", ("cv", "cover_letter"))

    op.create_table(
        "job_questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("question_type", question_type, nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("status", application_status, nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id", "job_id", name="uq_application_candidate_job"),
    )

    op.create_table(
        "application_answers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["job_questions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", "question_id", name="uq_application_question"),
    )

    op.create_table(
        "application_education",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("institution", sa.String(length=200), nullable=False),
        sa.Column("degree", sa.String(length=120), nullable=True),
        sa.Column("field_of_study", sa.String(length=120), nullable=True),
        sa.Column("start_year", sa.Integer(), nullable=True),
        sa.Column("end_year", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "application_experience",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("company", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("start_year", sa.Integer(), nullable=True),
        sa.Column("end_year", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "application_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("kind", document_kind, nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", "kind", name="uq_application_document_kind"),
    )


def downgrade() -> None:
    op.drop_table("application_documents")
    op.drop_table("application_experience")
    op.drop_table("application_education")
    op.drop_table("application_answers")
    op.drop_table("applications")
    op.drop_table("job_questions")
    op.execute(sa.text("DROP TYPE IF EXISTS document_kind"))
    op.execute(sa.text("DROP TYPE IF EXISTS application_status"))
    op.execute(sa.text("DROP TYPE IF EXISTS question_type"))
