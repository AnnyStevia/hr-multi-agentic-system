"""Departments, employees, and job department foreign key.

Revision ID: 007_departments_employees
Revises: 006_candidate_phone
Create Date: 2026-08-19

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "007_departments_employees"
down_revision = "006_candidate_phone"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    department_status = sa.Enum("active", "inactive", name="department_status")
    employment_status = sa.Enum("active", "inactive", "on_leave", name="employment_status")
    if bind.dialect.name == "postgresql":
        department_status = postgresql.ENUM(
            "active", "inactive", name="department_status", create_type=False
        )
        employment_status = postgresql.ENUM(
            "active", "inactive", "on_leave", name="employment_status", create_type=False
        )
        op.execute(
            sa.text(
                """
                DO $$ BEGIN
                    CREATE TYPE department_status AS ENUM ('active', 'inactive');
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )
        op.execute(
            sa.text(
                """
                DO $$ BEGIN
                    CREATE TYPE employment_status AS ENUM ('active', 'inactive', 'on_leave');
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )

    op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("status", department_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.add_column("jobs", sa.Column("department_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_jobs_department_id",
        "jobs",
        "departments",
        ["department_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                """
                INSERT INTO departments (name, status)
                SELECT DISTINCT department, 'active'::department_status
                FROM jobs
                WHERE department IS NOT NULL AND BTRIM(department) <> ''
                ON CONFLICT (name) DO NOTHING
                """
            )
        )
        op.execute(
            sa.text(
                """
                UPDATE jobs
                SET department_id = departments.id
                FROM departments
                WHERE jobs.department IS NOT NULL
                  AND BTRIM(jobs.department) = departments.name
                """
            )
        )
    else:
        op.execute(
            sa.text(
                """
                INSERT INTO departments (name, status)
                SELECT DISTINCT department, 'active'
                FROM jobs
                WHERE department IS NOT NULL AND TRIM(department) <> ''
                """
            )
        )
        op.execute(
            sa.text(
                """
                UPDATE jobs
                SET department_id = (
                    SELECT departments.id FROM departments
                    WHERE departments.name = TRIM(jobs.department)
                )
                WHERE department IS NOT NULL AND TRIM(department) <> ''
                """
            )
        )

    op.drop_column("jobs", "department")

    op.create_table(
        "employees",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employee_number", sa.String(length=20), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.String(length=120), nullable=False),
        sa.Column("hire_date", sa.Date(), nullable=False),
        sa.Column("employment_status", employment_status, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_number"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("user_id", name="uq_employee_user_id"),
    )


def downgrade() -> None:
    op.drop_table("employees")
    op.add_column("jobs", sa.Column("department", sa.String(length=120), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE jobs
            SET department = (
                SELECT departments.name FROM departments
                WHERE departments.id = jobs.department_id
            )
            """
        )
    )
    op.drop_constraint("fk_jobs_department_id", "jobs", type_="foreignkey")
    op.drop_column("jobs", "department_id")
    op.drop_table("departments")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP TYPE IF EXISTS employment_status"))
        op.execute(sa.text("DROP TYPE IF EXISTS department_status"))
