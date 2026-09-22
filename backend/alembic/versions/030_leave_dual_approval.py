"""Add dual leave approval columns and manager_approved notification.

Revision ID: 030_leave_dual_approval
Revises: 029_leave_rejection_reason
Create Date: 2026-09-22

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "030_leave_dual_approval"
down_revision = "029_leave_rejection_reason"
branch_labels = None
depends_on = None

APPROVAL_STATUSES = ("pending", "approved", "rejected")


def upgrade() -> None:
    bind = op.get_bind()

    approval_status = sa.Enum(*APPROVAL_STATUSES, name="leave_approval_status")
    if bind.dialect.name == "postgresql":
        approval_status = postgresql.ENUM(
            *APPROVAL_STATUSES,
            name="leave_approval_status",
            create_type=False,
        )
        op.execute(
            sa.text(
                """
                DO $$ BEGIN
                    CREATE TYPE leave_approval_status AS ENUM (
                        'pending', 'approved', 'rejected'
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
                    ALTER TYPE notification_type ADD VALUE 'leave_request_manager_approved';
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )
    else:
        approval_status.create(bind, checkfirst=True)

    op.add_column(
        "leave_requests",
        sa.Column(
            "manager_approval",
            approval_status,
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "leave_requests",
        sa.Column("manager_approved_by", sa.Integer(), nullable=True),
    )
    op.add_column(
        "leave_requests",
        sa.Column("manager_approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "leave_requests",
        sa.Column(
            "hr_approval",
            approval_status,
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "leave_requests",
        sa.Column("hr_approved_by", sa.Integer(), nullable=True),
    )
    op.add_column(
        "leave_requests",
        sa.Column("hr_approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "leave_requests",
        sa.Column(
            "admin_override",
            approval_status,
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "leave_requests",
        sa.Column("admin_approved_by", sa.Integer(), nullable=True),
    )
    op.add_column(
        "leave_requests",
        sa.Column("admin_approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_leave_requests_manager_approved_by",
        "leave_requests",
        "users",
        ["manager_approved_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_leave_requests_hr_approved_by",
        "leave_requests",
        "users",
        ["hr_approved_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_leave_requests_admin_approved_by",
        "leave_requests",
        "users",
        ["admin_approved_by"],
        ["id"],
        ondelete="SET NULL",
    )

    # Best-effort backfill: approved rows mark admin_override if reviewed_by set.
    op.execute(
        sa.text(
            """
            UPDATE leave_requests
            SET admin_override = 'approved',
                admin_approved_by = reviewed_by,
                admin_approved_at = approved_at
            WHERE status = 'approved' AND reviewed_by IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_constraint("fk_leave_requests_admin_approved_by", "leave_requests", type_="foreignkey")
    op.drop_constraint("fk_leave_requests_hr_approved_by", "leave_requests", type_="foreignkey")
    op.drop_constraint(
        "fk_leave_requests_manager_approved_by", "leave_requests", type_="foreignkey"
    )
    op.drop_column("leave_requests", "admin_approved_at")
    op.drop_column("leave_requests", "admin_approved_by")
    op.drop_column("leave_requests", "admin_override")
    op.drop_column("leave_requests", "hr_approved_at")
    op.drop_column("leave_requests", "hr_approved_by")
    op.drop_column("leave_requests", "hr_approval")
    op.drop_column("leave_requests", "manager_approved_at")
    op.drop_column("leave_requests", "manager_approved_by")
    op.drop_column("leave_requests", "manager_approval")

    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        sa.Enum(name="leave_approval_status").drop(bind, checkfirst=True)
