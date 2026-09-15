"""Repair legacy interview rows with inconsistent slot and status data.

Revision ID: 011_repair_interview_state
Revises: 010_interview_enhancements
Create Date: 2026-08-23

"""

from alembic import op
import sqlalchemy as sa

revision = "011_repair_interview_state"
down_revision = "010_interview_enhancements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE interviews
            SET status = 'scheduled'
            WHERE selected_slot_id IS NOT NULL
              AND status = 'proposed'
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE interview_slots AS slot
            SET is_selected = TRUE
            FROM interviews AS interview
            WHERE interview.id = slot.interview_id
              AND interview.selected_slot_id = slot.id
              AND slot.is_selected = FALSE
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE interview_slots AS slot
            SET is_available = FALSE
            FROM interviews AS interview
            WHERE interview.id = slot.interview_id
              AND interview.selected_slot_id IS NOT NULL
              AND slot.id <> interview.selected_slot_id
              AND slot.is_available = TRUE
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE interviews AS interview
            SET created_by_user_id = employee.user_id
            FROM employees AS employee
            WHERE interview.interviewer_employee_id = employee.id
              AND interview.created_by_user_id IS NULL
              AND employee.user_id IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    pass
