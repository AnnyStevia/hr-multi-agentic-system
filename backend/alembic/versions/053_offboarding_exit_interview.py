"""Create exit_interviews table and notification types.

Revision ID: 053_offboarding_exit_interview
Revises: 052_offboarding_clearance
Create Date: 2026-09-29

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "053_offboarding_exit_interview"
down_revision = "052_offboarding_clearance"
branch_labels = None
depends_on = None

STATUS_VALUES = (
    "scheduled",
    "completed",
    "cancelled",
)
NOTIFICATION_VALUES = (
    "exit_interview_scheduled",
    "exit_interview_meeting_ready",
)


def upgrade() -> None:
    bind = op.get_bind()
    status_enum = sa.Enum(*STATUS_VALUES, name="exit_interview_status")
    if bind.dialect.name == "postgresql":
        status_enum = postgresql.ENUM(
            *STATUS_VALUES,
            name="exit_interview_status",
            create_type=False,
        )
        op.execute(
            sa.text(
                """
                DO $$ BEGIN
                    CREATE TYPE exit_interview_status AS ENUM (
                        'scheduled',
                        'completed',
                        'cancelled'
                    );
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )
        for value in NOTIFICATION_VALUES:
            op.execute(
                sa.text(
                    f"ALTER TYPE notification_type ADD VALUE IF NOT EXISTS '{value}'"
                )
            )

    op.create_table(
        "exit_interviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("offboarding_case_id", sa.Integer(), nullable=False),
        sa.Column("interviewer_employee_id", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("meeting_url", sa.String(length=1000), nullable=True),
        sa.Column("meeting_external_id", sa.String(length=255), nullable=True),
        sa.Column("status", status_enum, nullable=False),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["offboarding_case_id"], ["offboarding_cases.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["interviewer_employee_id"], ["employees.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_exit_interviews_offboarding_case_id",
        "exit_interviews",
        ["offboarding_case_id"],
    )
    op.create_index(
        "ix_exit_interviews_interviewer_employee_id",
        "exit_interviews",
        ["interviewer_employee_id"],
    )
    op.create_index("ix_exit_interviews_status", "exit_interviews", ["status"])
    op.create_index(
        "uq_exit_interviews_one_active_per_case",
        "exit_interviews",
        ["offboarding_case_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('scheduled', 'completed')"),
        sqlite_where=sa.text("status IN ('scheduled', 'completed')"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_exit_interviews_one_active_per_case",
        table_name="exit_interviews",
    )
    op.drop_index("ix_exit_interviews_status", table_name="exit_interviews")
    op.drop_index(
        "ix_exit_interviews_interviewer_employee_id",
        table_name="exit_interviews",
    )
    op.drop_index(
        "ix_exit_interviews_offboarding_case_id",
        table_name="exit_interviews",
    )
    op.drop_table("exit_interviews")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP TYPE IF EXISTS exit_interview_status"))
