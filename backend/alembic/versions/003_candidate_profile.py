"""Candidate profile and candidate role

Revision ID: 003_candidate_profile
Revises: 002_recruitment_jobs
Create Date: 2026-08-18

"""

from alembic import op
import sqlalchemy as sa

revision = "003_candidate_profile"
down_revision = "002_recruitment_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "candidates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )

    roles = sa.table(
        "roles",
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
    )
    bind = op.get_bind()
    exists = bind.execute(sa.text("SELECT 1 FROM roles WHERE name = 'candidate'")).first()
    if exists is None:
        op.bulk_insert(
            roles,
            [{"name": "candidate", "description": "External job applicant"}],
        )


def downgrade() -> None:
    op.drop_table("candidates")
    op.execute(sa.text("DELETE FROM roles WHERE name = 'candidate'"))
