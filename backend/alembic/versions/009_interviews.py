"""Interviews and interview slots.

Revision ID: 009_interviews
Revises: 008_notifications
Create Date: 2026-08-23

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "009_interviews"
down_revision = "008_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    interview_status = sa.Enum(
        "proposed",
        "scheduled",
        "completed",
        "cancelled",
        name="interview_status",
    )
    if bind.dialect.name == "postgresql":
        interview_status = postgresql.ENUM(
            "proposed",
            "scheduled",
            "completed",
            "cancelled",
            name="interview_status",
            create_type=False,
        )
        op.execute(
            sa.text(
                """
                DO $$ BEGIN
                    CREATE TYPE interview_status AS ENUM (
                        'proposed',
                        'scheduled',
                        'completed',
                        'cancelled'
                    );
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )

    op.create_table(
        "interviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("interviewer_employee_id", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", interview_status, nullable=False, server_default="proposed"),
        sa.Column("selected_slot_id", sa.Integer(), nullable=True),
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
            ["application_id"],
            ["applications.id"],
            name="fk_interviews_application_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["interviewer_employee_id"],
            ["employees.id"],
            name="fk_interviews_interviewer_employee_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_interviews_application_id", "interviews", ["application_id"], unique=False)

    op.create_table(
        "interview_slots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("interview_id", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_selected", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["interview_id"],
            ["interviews.id"],
            name="fk_interview_slots_interview_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_interview_slots_interview_id", "interview_slots", ["interview_id"], unique=False)

    op.create_foreign_key(
        "fk_interviews_selected_slot_id",
        "interviews",
        "interview_slots",
        ["selected_slot_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_interviews_selected_slot_id", "interviews", type_="foreignkey")
    op.drop_index("ix_interview_slots_interview_id", table_name="interview_slots")
    op.drop_table("interview_slots")
    op.drop_index("ix_interviews_application_id", table_name="interviews")
    op.drop_table("interviews")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP TYPE IF EXISTS interview_status"))
