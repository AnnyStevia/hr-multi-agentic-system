"""Extend employees with profile fields; add education and experience tables.

Revision ID: 022_employee_profile
Revises: 021_onboarding_notifications
Create Date: 2026-09-18

"""

from alembic import op
import sqlalchemy as sa

revision = "022_employee_profile"
down_revision = "021_onboarding_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("employees", sa.Column("date_of_birth", sa.Date(), nullable=True))
    op.add_column("employees", sa.Column("address", sa.String(length=255), nullable=True))
    op.add_column("employees", sa.Column("city", sa.String(length=100), nullable=True))
    op.add_column("employees", sa.Column("country", sa.String(length=100), nullable=True))
    op.add_column(
        "employees",
        sa.Column("profile_picture_storage_key", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "employees",
        sa.Column("profile_picture_content_type", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "employees",
        sa.Column("profile_picture_filename", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "employees",
        sa.Column("profile_picture_size_bytes", sa.Integer(), nullable=True),
    )

    op.create_table(
        "employee_educations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "employee_id",
            sa.Integer(),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("institution", sa.String(length=200), nullable=False),
        sa.Column("degree", sa.String(length=200), nullable=False),
        sa.Column("field_of_study", sa.String(length=200), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "employee_experiences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "employee_id",
            sa.Integer(),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("company", sa.String(length=200), nullable=False),
        sa.Column("position", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("employee_experiences")
    op.drop_table("employee_educations")
    op.drop_column("employees", "profile_picture_size_bytes")
    op.drop_column("employees", "profile_picture_filename")
    op.drop_column("employees", "profile_picture_content_type")
    op.drop_column("employees", "profile_picture_storage_key")
    op.drop_column("employees", "country")
    op.drop_column("employees", "city")
    op.drop_column("employees", "address")
    op.drop_column("employees", "date_of_birth")
