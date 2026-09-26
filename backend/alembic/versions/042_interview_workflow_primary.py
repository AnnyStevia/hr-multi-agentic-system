"""Interview workflow: primary flag, structured feedback, assignment notifications (Phase 6.4C).

Revision ID: 042_interview_workflow_primary
Revises: 041_interview_interviewers
Create Date: 2026-09-26

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "042_interview_workflow_primary"
down_revision = "041_interview_interviewers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for value in ("interview_assignment",):
        op.execute(
            sa.text(
                f"""
                DO $$ BEGIN
                    ALTER TYPE notification_type ADD VALUE IF NOT EXISTS '{value}';
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )

    recommendation = postgresql.ENUM(
        "proceed",
        "additional_interview",
        "do_not_proceed",
        name="interviewer_recommendation",
        create_type=False,
    )
    op.execute(
        sa.text(
            """
            DO $$ BEGIN
                CREATE TYPE interviewer_recommendation AS ENUM (
                    'proceed',
                    'additional_interview',
                    'do_not_proceed'
                );
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
    )

    op.add_column(
        "interview_interviewers",
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.execute(
        sa.text(
            """
            UPDATE interview_interviewers AS ii
            SET is_primary = TRUE
            FROM interviews AS i
            WHERE ii.interview_id = i.id
              AND i.interviewer_employee_id IS NOT NULL
              AND ii.employee_id = i.interviewer_employee_id
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE interview_interviewers AS ii
            SET is_primary = TRUE
            WHERE ii.is_primary = FALSE
              AND ii.id = (
                    SELECT MIN(ii2.id)
                    FROM interview_interviewers AS ii2
                    WHERE ii2.interview_id = ii.interview_id
              )
              AND NOT EXISTS (
                    SELECT 1
                    FROM interview_interviewers AS ii3
                    WHERE ii3.interview_id = ii.interview_id
                      AND ii3.is_primary = TRUE
              )
            """
        )
    )
    op.create_index(
        "uq_interview_interviewers_one_primary",
        "interview_interviewers",
        ["interview_id"],
        unique=True,
        postgresql_where=sa.text("is_primary = true"),
    )

    op.alter_column("interviews", "message", existing_type=sa.Text(), nullable=True)
    op.add_column("interviews", sa.Column("tech_knowledge", sa.Integer(), nullable=True))
    op.add_column("interviews", sa.Column("communication", sa.Integer(), nullable=True))
    op.add_column("interviews", sa.Column("problem_solving", sa.Integer(), nullable=True))
    op.add_column("interviews", sa.Column("relevant_experience", sa.Integer(), nullable=True))
    op.add_column("interviews", sa.Column("strengths", sa.Text(), nullable=True))
    op.add_column("interviews", sa.Column("weaknesses", sa.Text(), nullable=True))
    op.add_column("interviews", sa.Column("additional_comments", sa.Text(), nullable=True))
    op.add_column(
        "interviews",
        sa.Column("recommendation", recommendation, nullable=True),
    )
    op.add_column(
        "interviews",
        sa.Column("completed_by_employee_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_interviews_completed_by_employee_id",
        "interviews",
        "employees",
        ["completed_by_employee_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.drop_constraint("fk_interviews_completed_by_employee_id", "interviews", type_="foreignkey")
    op.drop_column("interviews", "completed_by_employee_id")
    op.drop_column("interviews", "recommendation")
    op.drop_column("interviews", "additional_comments")
    op.drop_column("interviews", "weaknesses")
    op.drop_column("interviews", "strengths")
    op.drop_column("interviews", "relevant_experience")
    op.drop_column("interviews", "problem_solving")
    op.drop_column("interviews", "communication")
    op.drop_column("interviews", "tech_knowledge")
    op.alter_column("interviews", "message", existing_type=sa.Text(), nullable=False)

    op.drop_index("uq_interview_interviewers_one_primary", table_name="interview_interviewers")
    op.drop_column("interview_interviewers", "is_primary")
    op.execute(sa.text("DROP TYPE IF EXISTS interviewer_recommendation"))
