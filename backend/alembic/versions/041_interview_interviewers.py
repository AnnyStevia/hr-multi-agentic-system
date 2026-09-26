"""Add interview_interviewers association and meeting_url (Phase 6.4A).

Revision ID: 041_interview_interviewers
Revises: 040_application_fit_assessment
Create Date: 2026-09-26

"""

from alembic import op
import sqlalchemy as sa

revision = "041_interview_interviewers"
down_revision = "040_application_fit_assessment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.add_column("interviews", sa.Column("meeting_url", sa.String(length=1000), nullable=True))

    op.create_table(
        "interview_interviewers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("interview_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["interview_id"],
            ["interviews.id"],
            name="fk_interview_interviewers_interview_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
            name="fk_interview_interviewers_employee_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "interview_id",
            "employee_id",
            name="uq_interview_interviewers_interview_employee",
        ),
    )
    op.create_index(
        "ix_interview_interviewers_interview_id",
        "interview_interviewers",
        ["interview_id"],
        unique=False,
    )
    op.create_index(
        "ix_interview_interviewers_employee_id",
        "interview_interviewers",
        ["employee_id"],
        unique=False,
    )

    op.execute(
        sa.text(
            """
            INSERT INTO interview_interviewers (interview_id, employee_id)
            SELECT i.id, i.interviewer_employee_id
            FROM interviews i
            WHERE i.interviewer_employee_id IS NOT NULL
              AND NOT EXISTS (
                    SELECT 1
                    FROM interview_interviewers ii
                    WHERE ii.interview_id = i.id
                      AND ii.employee_id = i.interviewer_employee_id
              )
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.drop_index("ix_interview_interviewers_employee_id", table_name="interview_interviewers")
    op.drop_index("ix_interview_interviewers_interview_id", table_name="interview_interviewers")
    op.drop_table("interview_interviewers")
    op.drop_column("interviews", "meeting_url")
