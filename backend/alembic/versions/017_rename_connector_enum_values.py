"""Rename SourceType enum values to canonical connector vocabulary.

upload -> manual_drop  (aligns enum with registry key, dispatch, and UI)
directory -> file_system  (aligns enum with registry key and UI)

PostgreSQL 10+ supports ALTER TYPE ... RENAME VALUE inside a transaction,
so no autocommit workaround is needed (unlike ADD VALUE).

Revision ID: 017_rename_connector_enum_values
Revises: 016_p7_sync_failures
Create Date: 2026-04-21
"""
from typing import Sequence, Union
from alembic import op

revision: str = '017_rename_connector_enum_values'
down_revision: Union[str, None] = '016_p7_sync_failures'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # source_type is a SHARED (CivicCore-owned) enum. On a fresh install the
    # civiccore baseline declares it with the canonical post-rename values
    # ('manual_drop', 'file_system') already, so 'upload'/'directory' do not
    # exist and the bare RENAME would raise. Gate each rename on the source
    # value's presence in pg_enum so the migration is a no-op when the
    # values already match the target shape.
    op.execute(
        "DO $$ BEGIN "
        "IF EXISTS (SELECT 1 FROM pg_enum e "
        "JOIN pg_type t ON e.enumtypid = t.oid "
        "WHERE t.typname = 'source_type' AND e.enumlabel = 'upload') THEN "
        "  ALTER TYPE source_type RENAME VALUE 'upload' TO 'manual_drop'; "
        "END IF; END $$;"
    )
    op.execute(
        "DO $$ BEGIN "
        "IF EXISTS (SELECT 1 FROM pg_enum e "
        "JOIN pg_type t ON e.enumtypid = t.oid "
        "WHERE t.typname = 'source_type' AND e.enumlabel = 'directory') THEN "
        "  ALTER TYPE source_type RENAME VALUE 'directory' TO 'file_system'; "
        "END IF; END $$;"
    )


def downgrade() -> None:
    op.execute("ALTER TYPE source_type RENAME VALUE 'manual_drop' TO 'upload'")
    op.execute("ALTER TYPE source_type RENAME VALUE 'file_system' TO 'directory'")
