"""Add approved-leave cancellation workflow fields (Phase 5.12).

Revision ID: 037_leave_cancellation
Revises: 036_company_document_rag_index
Create Date: 2026-09-25

"""

from alembic import op
import sqlalchemy as sa

revision = "037_leave_cancellation"
down_revision = "036_company_document_rag_index"
branch_labels = None
depends_on = None

_CANCELLATION_STATUS = sa.Enum(
    "none",
    "requested",
    "rejected",
    name="leave_cancellation_status",
)

_NEW_NOTIFICATION_TYPES = (
    "leave_cancellation_requested",
    "leave_cancellation_approved",
    "leave_cancellation_rejected",
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    _CANCELLATION_STATUS.create(bind, checkfirst=True)
    op.add_column(
        "leave_requests",
        sa.Column(
            "cancellation_status",
            _CANCELLATION_STATUS,
            nullable=False,
            server_default="none",
        ),
    )
    op.add_column(
        "leave_requests",
        sa.Column("cancellation_requested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "leave_requests",
        sa.Column(
            "cancellation_requested_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "leave_requests",
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "leave_requests",
        sa.Column("cancellation_processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "leave_requests",
        sa.Column(
            "cancellation_processed_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "leave_requests",
        sa.Column("cancellation_rejection_reason", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_leave_requests_cancellation_status",
        "leave_requests",
        ["cancellation_status"],
    )

    for value in _NEW_NOTIFICATION_TYPES:
        op.execute(
            sa.text(
                f"ALTER TYPE notification_type ADD VALUE IF NOT EXISTS '{value}'"
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.drop_index("ix_leave_requests_cancellation_status", table_name="leave_requests")
    op.drop_column("leave_requests", "cancellation_rejection_reason")
    op.drop_column("leave_requests", "cancellation_processed_by")
    op.drop_column("leave_requests", "cancellation_processed_at")
    op.drop_column("leave_requests", "cancellation_reason")
    op.drop_column("leave_requests", "cancellation_requested_by")
    op.drop_column("leave_requests", "cancellation_requested_at")
    op.drop_column("leave_requests", "cancellation_status")
    _CANCELLATION_STATUS.drop(bind, checkfirst=True)
