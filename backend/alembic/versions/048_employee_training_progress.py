"""Create employee_training_progress for per-employee completion.

Revision ID: 048_employee_training_progress
Revises: 047_training_resource_published
Create Date: 2026-09-28

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "048_employee_training_progress"
down_revision = "047_training_resource_published"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    status_enum = sa.Enum("pending", "completed", name="employee_training_status")
    if bind.dialect.name == "postgresql":
        status_enum = postgresql.ENUM(
            "pending",
            "completed",
            name="employee_training_status",
            create_type=False,
        )
        op.execute(
            sa.text(
                """
                DO $$ BEGIN
                    CREATE TYPE employee_training_status AS ENUM ('pending', 'completed');
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )

    op.create_table(
        "employee_training_progress",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("training_id", sa.Integer(), nullable=False),
        sa.Column("status", status_enum, nullable=False),
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
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["training_id"], ["trainings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id", "training_id", name="uq_employee_training_progress"),
    )
    op.create_index(
        "ix_employee_training_progress_employee_id",
        "employee_training_progress",
        ["employee_id"],
    )
    op.create_index(
        "ix_employee_training_progress_training_id",
        "employee_training_progress",
        ["training_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_employee_training_progress_training_id",
        table_name="employee_training_progress",
    )
    op.drop_index(
        "ix_employee_training_progress_employee_id",
        table_name="employee_training_progress",
    )
    op.drop_table("employee_training_progress")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP TYPE IF EXISTS employee_training_status"))
