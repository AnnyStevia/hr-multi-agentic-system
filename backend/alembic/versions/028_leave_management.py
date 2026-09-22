"""Add leave management tables and notification types.

Revision ID: 028_leave_management
Revises: 027_meet_manager_optional
Create Date: 2026-09-22

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "028_leave_management"
down_revision = "027_meet_manager_optional"
branch_labels = None
depends_on = None

LEAVE_REQUEST_STATUSES = ("pending", "approved", "rejected", "cancelled")
LEAVE_NOTIFICATION_TYPES = (
    "leave_request_submitted",
    "leave_request_approved",
    "leave_request_rejected",
    "leave_request_cancelled",
)


def upgrade() -> None:
    bind = op.get_bind()

    leave_status = sa.Enum(*LEAVE_REQUEST_STATUSES, name="leave_request_status")
    if bind.dialect.name == "postgresql":
        leave_status = postgresql.ENUM(
            *LEAVE_REQUEST_STATUSES,
            name="leave_request_status",
            create_type=False,
        )
        op.execute(
            sa.text(
                """
                DO $$ BEGIN
                    CREATE TYPE leave_request_status AS ENUM (
                        'pending', 'approved', 'rejected', 'cancelled'
                    );
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )
        for value in LEAVE_NOTIFICATION_TYPES:
            op.execute(
                sa.text(
                    f"""
                    DO $$ BEGIN
                        ALTER TYPE notification_type ADD VALUE '{value}';
                    EXCEPTION WHEN duplicate_object THEN NULL;
                    END $$;
                    """
                )
            )
    else:
        leave_status.create(bind, checkfirst=True)

    op.create_table(
        "leave_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_paid", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.UniqueConstraint("name", name="uq_leave_types_name"),
    )

    op.create_table(
        "leave_policies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("leave_type_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("days_allowed", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["leave_type_id"],
            ["leave_types.id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("leave_type_id", "year", name="uq_leave_policies_type_year"),
        sa.CheckConstraint("year >= 2000 AND year <= 2100", name="ck_leave_policies_year"),
        sa.CheckConstraint(
            "days_allowed >= 0 AND days_allowed <= 365",
            name="ck_leave_policies_days_allowed",
        ),
    )
    op.create_index("ix_leave_policies_leave_type_id", "leave_policies", ["leave_type_id"])
    op.create_index("ix_leave_policies_year", "leave_policies", ["year"])

    op.create_table(
        "leave_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("leave_type_id", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("requested_days", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", leave_status, nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["leave_type_id"],
            ["leave_types.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.CheckConstraint("end_date >= start_date", name="ck_leave_requests_date_order"),
        sa.CheckConstraint("requested_days >= 1", name="ck_leave_requests_requested_days"),
    )
    op.create_index(
        "ix_leave_requests_employee_status",
        "leave_requests",
        ["employee_id", "status"],
    )
    op.create_index("ix_leave_requests_leave_type_id", "leave_requests", ["leave_type_id"])
    op.create_index(
        "ix_leave_requests_dates",
        "leave_requests",
        ["start_date", "end_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_leave_requests_dates", table_name="leave_requests")
    op.drop_index("ix_leave_requests_leave_type_id", table_name="leave_requests")
    op.drop_index("ix_leave_requests_employee_status", table_name="leave_requests")
    op.drop_table("leave_requests")
    op.drop_index("ix_leave_policies_year", table_name="leave_policies")
    op.drop_index("ix_leave_policies_leave_type_id", table_name="leave_policies")
    op.drop_table("leave_policies")
    op.drop_table("leave_types")

    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        sa.Enum(name="leave_request_status").drop(bind, checkfirst=True)
