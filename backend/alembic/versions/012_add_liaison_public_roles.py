"""Add liaison and public values to user_role enum

Revision ID: 012_liaison_public_roles
Revises: 011_fix_drift
Create Date: 2026-04-14

The UserRole Python enum has always declared LIAISON and PUBLIC, but the
Postgres user_role type was created in migration 001 with only four values:
admin, staff, reviewer, read_only.  Any attempt to INSERT a user with role
'liaison' or 'public' via the live database raises:

    invalid input value for enum user_role: "liaison"

This migration adds the two missing values.  ALTER TYPE … ADD VALUE is
transactional in Postgres 12+ only when not inside an explicit transaction;
Alembic executes DDL inside a transaction by default, so we must use
execute_if / non-transactional DDL or simply add the values unconditionally
with IF NOT EXISTS (Postgres 9.6+).
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op


revision: str = '012_liaison_public_roles'
down_revision: Union[str, None] = '011_fix_drift'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL 12+ allows ALTER TYPE ... ADD VALUE IF NOT EXISTS inside a transaction.
    # The project targets PostgreSQL 17, so the prior COMMIT workaround (which breaks
    # asyncpg's protocol-level transaction management) is not needed.
    #
    # The user_role enum is a SHARED (CivicCore-owned) type — civiccore baseline
    # already declares the full role set including 'liaison' and 'public', so on
    # any DB that ran the baseline these statements no-op via ADD VALUE IF NOT
    # EXISTS. Native Postgres idempotency is sufficient here; no `has_table`
    # gate is needed because we are mutating a TYPE, not a table.
    op.execute(sa.text("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'liaison'"))
    op.execute(sa.text("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'public'"))


def downgrade() -> None:
    # Postgres does not support DROP VALUE from an enum type.
    # A full downgrade would require recreating the type without the values,
    # which is destructive.  Leave as no-op and document the constraint.
    pass
