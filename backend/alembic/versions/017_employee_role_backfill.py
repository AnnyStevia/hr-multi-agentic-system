"""Backfill employee role for users linked to employee records.



Revision ID: 017_employee_role_backfill

Revises: 016_onboarding_backfill

Create Date: 2026-09-16



"""



from alembic import op

import sqlalchemy as sa



revision = "017_employee_role_backfill"

down_revision = "016_onboarding_backfill"

branch_labels = None

depends_on = None





def upgrade() -> None:

    bind = op.get_bind()

    roles = sa.table(

        "roles",

        sa.column("id", sa.Integer),

        sa.column("name", sa.String),

    )

    employees = sa.table(

        "employees",

        sa.column("user_id", sa.Integer),

    )

    user_roles = sa.table(

        "user_roles",

        sa.column("user_id", sa.Integer),

        sa.column("role_id", sa.Integer),

    )



    employee_role_id = bind.execute(

        sa.select(roles.c.id).where(roles.c.name == "employee")

    ).scalar()

    if employee_role_id is None:

        return



    linked_user_ids = (

        bind.execute(

            sa.select(employees.c.user_id).where(employees.c.user_id.is_not(None))

        )

        .scalars()

        .all()

    )

    if not linked_user_ids:

        return



    existing = set(

        bind.execute(

            sa.select(user_roles.c.user_id).where(

                user_roles.c.role_id == employee_role_id,

                user_roles.c.user_id.in_(linked_user_ids),

            )

        )

        .scalars()

        .all()

    )



    for user_id in linked_user_ids:

        if user_id in existing:

            continue

        bind.execute(

            user_roles.insert().values(user_id=user_id, role_id=employee_role_id)

        )





def downgrade() -> None:

    pass

