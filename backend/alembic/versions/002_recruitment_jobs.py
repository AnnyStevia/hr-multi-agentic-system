"""Recruitment jobs schema

Revision ID: 002_recruitment_jobs
Revises: 001_initial_identity
Create Date: 2026-08-18

"""

from alembic import op
import sqlalchemy as sa

revision = "002_recruitment_jobs"
down_revision = "001_initial_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("department", sa.String(length=120), nullable=True),
        sa.Column("position", sa.String(length=120), nullable=True),
        sa.Column("location", sa.String(length=120), nullable=True),
        sa.Column(
            "employment_type",
            sa.Enum("full_time", "part_time", "contract", "internship", name="employment_type"),
            nullable=False,
        ),
        sa.Column("requirements", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("draft", "published", "closed", name="job_status"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("jobs")
    sa.Enum(name="employment_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="job_status").drop(op.get_bind(), checkfirst=True)
