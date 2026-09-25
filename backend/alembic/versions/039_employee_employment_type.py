"""Add employment_type and employment_end_date to employees (Phase 5.12).

Revision ID: 039_employee_employment_type
Revises: 038_job_internship_duration
Create Date: 2026-09-25

"""

from alembic import op
import sqlalchemy as sa

revision = "039_employee_employment_type"
down_revision = "038_job_internship_duration"
branch_labels = None
depends_on = None

# Reuse existing PostgreSQL enum `employment_type` from jobs.
_EMPLOYMENT_TYPE = sa.Enum(
    "full_time",
    "part_time",
    "contract",
    "internship",
    name="employment_type",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.add_column(
        "employees",
        sa.Column(
            "employment_type",
            _EMPLOYMENT_TYPE,
            nullable=False,
            server_default="full_time",
        ),
    )
    op.add_column(
        "employees",
        sa.Column("employment_end_date", sa.Date(), nullable=True),
    )
    op.create_index(
        "ix_employees_employment_type",
        "employees",
        ["employment_type"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.drop_index("ix_employees_employment_type", table_name="employees")
    op.drop_column("employees", "employment_end_date")
    op.drop_column("employees", "employment_type")
