"""Create offboarding_cases foundation table.

Revision ID: 049_offboarding_cases
Revises: 048_employee_training_progress
Create Date: 2026-09-29

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "049_offboarding_cases"
down_revision = "048_employee_training_progress"
branch_labels = None
depends_on = None

REASON_VALUES = (
    "resignation",
    "end_of_contract",
    "termination",
    "retirement",
    "other",
)
STATUS_VALUES = (
    "initiated",
    "in_progress",
    "pending_clearance",
    "completed",
    "cancelled",
)


def upgrade() -> None:
    bind = op.get_bind()
    reason_enum = sa.Enum(*REASON_VALUES, name="offboarding_reason")
    status_enum = sa.Enum(*STATUS_VALUES, name="offboarding_status")
    if bind.dialect.name == "postgresql":
        reason_enum = postgresql.ENUM(
            *REASON_VALUES,
            name="offboarding_reason",
            create_type=False,
        )
        status_enum = postgresql.ENUM(
            *STATUS_VALUES,
            name="offboarding_status",
            create_type=False,
        )
        op.execute(
            sa.text(
                """
                DO $$ BEGIN
                    CREATE TYPE offboarding_reason AS ENUM (
                        'resignation',
                        'end_of_contract',
                        'termination',
                        'retirement',
                        'other'
                    );
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )
        op.execute(
            sa.text(
                """
                DO $$ BEGIN
                    CREATE TYPE offboarding_status AS ENUM (
                        'initiated',
                        'in_progress',
                        'pending_clearance',
                        'completed',
                        'cancelled'
                    );
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )

    op.create_table(
        "offboarding_cases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("reason", reason_enum, nullable=False),
        sa.Column("reason_details", sa.Text(), nullable=True),
        sa.Column("last_working_day", sa.Date(), nullable=False),
        sa.Column("status", status_enum, nullable=False),
        sa.Column("initiated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_offboarding_cases_employee_id",
        "offboarding_cases",
        ["employee_id"],
    )
    op.create_index(
        "ix_offboarding_cases_status",
        "offboarding_cases",
        ["status"],
    )

    # Defense in depth: at most one active case per employee.
    # Active = initiated | in_progress | pending_clearance.
    # Service layer also enforces this (required for SQLite tests).
    if bind.dialect.name == "postgresql":
        op.create_index(
            "uq_offboarding_cases_one_active_per_employee",
            "offboarding_cases",
            ["employee_id"],
            unique=True,
            postgresql_where=sa.text(
                "status IN ('initiated', 'in_progress', 'pending_clearance')"
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_index(
            "uq_offboarding_cases_one_active_per_employee",
            table_name="offboarding_cases",
        )
    op.drop_index("ix_offboarding_cases_status", table_name="offboarding_cases")
    op.drop_index("ix_offboarding_cases_employee_id", table_name="offboarding_cases")
    op.drop_table("offboarding_cases")
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP TYPE IF EXISTS offboarding_status"))
        op.execute(sa.text("DROP TYPE IF EXISTS offboarding_reason"))
