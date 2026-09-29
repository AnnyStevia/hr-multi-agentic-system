"""Create offboarding_requests table and notification types.

Revision ID: 051_offboarding_requests
Revises: 050_offboarding_tasks
Create Date: 2026-09-29

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "051_offboarding_requests"
down_revision = "050_offboarding_tasks"
branch_labels = None
depends_on = None

REQUEST_STATUS_VALUES = (
    "pending",
    "approved",
    "rejected",
    "cancelled",
)
REASON_VALUES = (
    "resignation",
    "end_of_contract",
    "termination",
    "retirement",
    "other",
)
NOTIFICATION_VALUES = (
    "offboarding_request_submitted",
    "offboarding_request_approved",
    "offboarding_request_rejected",
)


def upgrade() -> None:
    bind = op.get_bind()
    request_status_enum = sa.Enum(*REQUEST_STATUS_VALUES, name="offboarding_request_status")
    reason_enum = sa.Enum(*REASON_VALUES, name="offboarding_reason")
    if bind.dialect.name == "postgresql":
        request_status_enum = postgresql.ENUM(
            *REQUEST_STATUS_VALUES,
            name="offboarding_request_status",
            create_type=False,
        )
        reason_enum = postgresql.ENUM(
            *REASON_VALUES,
            name="offboarding_reason",
            create_type=False,
        )
        op.execute(
            sa.text(
                """
                DO $$ BEGIN
                    CREATE TYPE offboarding_request_status AS ENUM (
                        'pending',
                        'approved',
                        'rejected',
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
        "offboarding_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("reason", reason_enum, nullable=False),
        sa.Column("reason_details", sa.Text(), nullable=True),
        sa.Column("requested_last_working_day", sa.Date(), nullable=False),
        sa.Column("status", request_status_enum, nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("offboarding_case_id", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["offboarding_case_id"], ["offboarding_cases.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_offboarding_requests_employee_id",
        "offboarding_requests",
        ["employee_id"],
    )
    op.create_index(
        "ix_offboarding_requests_status",
        "offboarding_requests",
        ["status"],
    )
    op.create_index(
        "ix_offboarding_requests_offboarding_case_id",
        "offboarding_requests",
        ["offboarding_case_id"],
    )
    op.create_index(
        "uq_offboarding_requests_one_pending_per_employee",
        "offboarding_requests",
        ["employee_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
        sqlite_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_offboarding_requests_one_pending_per_employee",
        table_name="offboarding_requests",
    )
    op.drop_index(
        "ix_offboarding_requests_offboarding_case_id",
        table_name="offboarding_requests",
    )
    op.drop_index("ix_offboarding_requests_status", table_name="offboarding_requests")
    op.drop_index(
        "ix_offboarding_requests_employee_id",
        table_name="offboarding_requests",
    )
    op.drop_table("offboarding_requests")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP TYPE IF EXISTS offboarding_request_status"))
