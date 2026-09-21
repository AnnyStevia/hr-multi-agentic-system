"""Add positions catalog and employee reporting links.

Revision ID: 023_organization_structure
Revises: 022_employee_profile
Create Date: 2026-09-21

"""

from alembic import op
import sqlalchemy as sa

revision = "023_organization_structure"
down_revision = "022_employee_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "positions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("department_id", sa.Integer(), nullable=True),
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
            ["department_id"],
            ["departments.id"],
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("title", name="uq_positions_title"),
    )
    op.create_index("ix_positions_department_id", "positions", ["department_id"])

    op.add_column("employees", sa.Column("position_id", sa.Integer(), nullable=True))
    op.add_column("employees", sa.Column("manager_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_employees_position_id_positions",
        "employees",
        "positions",
        ["position_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_employees_manager_id_employees",
        "employees",
        "employees",
        ["manager_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_employees_position_id", "employees", ["position_id"])
    op.create_index("ix_employees_manager_id", "employees", ["manager_id"])

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT DISTINCT position FROM employees "
            "WHERE position IS NOT NULL AND btrim(position) <> ''"
        )
    ).fetchall()
    for (title,) in rows:
        clean = title.strip()
        conn.execute(
            sa.text(
                "INSERT INTO positions (title, description, department_id) "
                "VALUES (:title, NULL, NULL) "
                "ON CONFLICT (title) DO NOTHING"
            ),
            {"title": clean},
        )
    conn.execute(
        sa.text(
            "UPDATE employees e "
            "SET position_id = p.id "
            "FROM positions p "
            "WHERE p.title = btrim(e.position) AND e.position_id IS NULL"
        )
    )


def downgrade() -> None:
    op.drop_constraint("fk_employees_manager_id_employees", "employees", type_="foreignkey")
    op.drop_constraint("fk_employees_position_id_positions", "employees", type_="foreignkey")
    op.drop_index("ix_employees_manager_id", table_name="employees")
    op.drop_index("ix_employees_position_id", table_name="employees")
    op.drop_column("employees", "manager_id")
    op.drop_column("employees", "position_id")
    op.drop_index("ix_positions_department_id", table_name="positions")
    op.drop_table("positions")
