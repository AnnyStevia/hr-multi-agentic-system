"""Add document_type and training_id for onboarding task verification.

Revision ID: 026_onboarding_task_verify
Revises: 025_application_submitted
Create Date: 2026-09-21

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "026_onboarding_task_verify"
down_revision = "025_application_submitted"
branch_labels = None
depends_on = None

DOCUMENT_TYPES = (
    "id_document",
    "contract",
    "diploma",
    "certificate",
    "other",
)


def upgrade() -> None:
    bind = op.get_bind()
    doc_type = sa.Enum(*DOCUMENT_TYPES, name="employee_document_type")
    if bind.dialect.name == "postgresql":
        doc_type = postgresql.ENUM(
            *DOCUMENT_TYPES,
            name="employee_document_type",
            create_type=False,
        )

    op.add_column(
        "onboarding_task_templates",
        sa.Column("document_type", doc_type, nullable=True),
    )
    op.add_column(
        "onboarding_task_templates",
        sa.Column("training_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_onboarding_task_templates_training_id",
        "onboarding_task_templates",
        "trainings",
        ["training_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "onboarding_tasks",
        sa.Column("document_type", doc_type, nullable=True),
    )
    op.add_column(
        "onboarding_tasks",
        sa.Column("training_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_onboarding_tasks_training_id",
        "onboarding_tasks",
        "trainings",
        ["training_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Seed / ensure Company orientation training
    op.execute(
        sa.text(
            """
            INSERT INTO trainings (title, description)
            SELECT 'Company orientation', 'Required company orientation for new hires.'
            WHERE NOT EXISTS (
                SELECT 1 FROM trainings WHERE title = 'Company orientation'
            )
            """
        )
    )

    # Backfill document template + snapshot tasks
    op.execute(
        sa.text(
            """
            UPDATE onboarding_task_templates
            SET document_type = 'id_document'
            WHERE title = 'Upload your identification document'
              AND task_type = 'document'
              AND document_type IS NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE onboarding_tasks AS t
            SET document_type = tpl.document_type
            FROM onboarding_task_templates AS tpl
            WHERE t.template_id = tpl.id
              AND tpl.document_type IS NOT NULL
              AND t.document_type IS NULL
            """
        )
    )

    # Link training template to Company orientation
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                """
                UPDATE onboarding_task_templates
                SET training_id = (
                    SELECT id FROM trainings WHERE title = 'Company orientation' LIMIT 1
                )
                WHERE title = 'Complete your assigned training'
                  AND task_type = 'training'
                  AND training_id IS NULL
                """
            )
        )
        op.execute(
            sa.text(
                """
                UPDATE onboarding_tasks AS t
                SET training_id = tpl.training_id
                FROM onboarding_task_templates AS tpl
                WHERE t.template_id = tpl.id
                  AND tpl.training_id IS NOT NULL
                  AND t.training_id IS NULL
                """
            )
        )
    else:
        # SQLite-friendly sequential updates
        training_id = bind.execute(
            sa.text("SELECT id FROM trainings WHERE title = 'Company orientation' LIMIT 1")
        ).scalar()
        if training_id is not None:
            bind.execute(
                sa.text(
                    """
                    UPDATE onboarding_task_templates
                    SET training_id = :tid
                    WHERE title = 'Complete your assigned training'
                      AND task_type = 'training'
                      AND training_id IS NULL
                    """
                ),
                {"tid": training_id},
            )
            bind.execute(
                sa.text(
                    """
                    UPDATE onboarding_tasks
                    SET training_id = (
                        SELECT training_id FROM onboarding_task_templates
                        WHERE onboarding_task_templates.id = onboarding_tasks.template_id
                    )
                    WHERE training_id IS NULL
                      AND template_id IS NOT NULL
                      AND EXISTS (
                        SELECT 1 FROM onboarding_task_templates
                        WHERE onboarding_task_templates.id = onboarding_tasks.template_id
                          AND onboarding_task_templates.training_id IS NOT NULL
                      )
                    """
                )
            )


def downgrade() -> None:
    op.drop_constraint("fk_onboarding_tasks_training_id", "onboarding_tasks", type_="foreignkey")
    op.drop_column("onboarding_tasks", "training_id")
    op.drop_column("onboarding_tasks", "document_type")
    op.drop_constraint(
        "fk_onboarding_task_templates_training_id",
        "onboarding_task_templates",
        type_="foreignkey",
    )
    op.drop_column("onboarding_task_templates", "training_id")
    op.drop_column("onboarding_task_templates", "document_type")
