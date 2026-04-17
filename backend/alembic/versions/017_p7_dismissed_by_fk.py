# backend/alembic/versions/017_p7_dismissed_by_fk.py
"""P7: restore ForeignKey on sync_failures.dismissed_by → users.id

Revision ID: 017_p7_dismissed_by_fk
Revises: 016_p7_sync_failures
Create Date: 2026-04-17

Migration 016 (commit 6e0d2d9) omitted the FK on dismissed_by because the
Task 1 test seeded a random uuid4() as the dismisser. That was wrong — the
test needed fixing, not the schema. Dismissal is a compliance artifact and
DB-enforced referential integrity to the users table is required.
"""
from typing import Sequence, Union

from alembic import op

revision: str = '017_p7_dismissed_by_fk'
down_revision: Union[str, None] = '016_p7_sync_failures'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_sync_failures_dismissed_by_users",
        "sync_failures",
        "users",
        ["dismissed_by"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_sync_failures_dismissed_by_users",
        "sync_failures",
        type_="foreignkey",
    )
