"""Add onboarding task templates catalogue and extend onboarding tasks.

Revision ID: 024_onboarding_task_templates
Revises: 023_organization_structure
Create Date: 2026-09-21

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "024_onboarding_task_templates"
down_revision = "023_organization_structure"
branch_labels = None
depends_on = None

TASK_TYPES = (
    "profile_personal_info",
    "profile_picture",
    "education",
    "experience",
    "document",
    "training",
    "acknowledgement",
    "manual",
)

DEFAULT_TEMPLATES = (
    ("Complete your personal information", "profile_personal_info", True),
    ("Add your profile picture", "profile_picture", True),
    ("Add your education", "education", True),
    ("Add your professional experience", "experience", True),
    ("Upload your identification document", "document", True),
    ("Complete your assigned training", "training", True),
    ("Read company policies", "acknowledgement", True),
    ("Meet your manager", "manual", False),
)


def upgrade() -> None:
    bind = op.get_bind()
    task_type = sa.Enum(*TASK_TYPES, name="onboarding_task_type")
    if bind.dialect.name == "postgresql":
        task_type = postgresql.ENUM(*TASK_TYPES, name="onboarding_task_type", create_type=False)
        op.execute(
            sa.text(
                """
                DO $$ BEGIN
                    CREATE TYPE onboarding_task_type AS ENUM (
                        'profile_personal_info',
                        'profile_picture',
                        'education',
                        'experience',
                        'document',
                        'training',
                        'acknowledgement',
                        'manual'
                    );
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )

    op.create_table(
        "onboarding_task_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("task_type", task_type, nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        sa.UniqueConstraint("title", name="uq_onboarding_task_templates_title"),
    )

    op.add_column(
        "onboarding_tasks",
        sa.Column("template_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "onboarding_tasks",
        sa.Column("task_type", task_type, nullable=True),
    )
    op.add_column(
        "onboarding_tasks",
        sa.Column(
            "is_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.create_foreign_key(
        "fk_onboarding_tasks_template_id",
        "onboarding_tasks",
        "onboarding_task_templates",
        ["template_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_onboarding_tasks_template_id", "onboarding_tasks", ["template_id"])

    op.execute(
        sa.text(
            "UPDATE onboarding_tasks SET task_type = 'manual' WHERE task_type IS NULL"
        )
    )
    # Make task_type non-null after backfill
    op.alter_column(
        "onboarding_tasks",
        "task_type",
        existing_type=task_type,
        nullable=False,
        server_default="manual",
    )

    for title, task_type_value, is_required in DEFAULT_TEMPLATES:
        op.execute(
            sa.text(
                """
                INSERT INTO onboarding_task_templates (title, description, task_type, is_required, is_active)
                SELECT :title, NULL, CAST(:task_type AS onboarding_task_type), :is_required, true
                WHERE NOT EXISTS (
                    SELECT 1 FROM onboarding_task_templates WHERE title = :title
                )
                """
            ).bindparams(
                title=title,
                task_type=task_type_value,
                is_required=is_required,
            )
        )


def downgrade() -> None:
    op.drop_constraint("fk_onboarding_tasks_template_id", "onboarding_tasks", type_="foreignkey")
    op.drop_index("ix_onboarding_tasks_template_id", table_name="onboarding_tasks")
    op.drop_column("onboarding_tasks", "is_required")
    op.drop_column("onboarding_tasks", "task_type")
    op.drop_column("onboarding_tasks", "template_id")
    op.drop_table("onboarding_task_templates")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP TYPE IF EXISTS onboarding_task_type"))
