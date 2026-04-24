"""Add last_sync_cursor and REST_API/ODBC source types

Revision ID: 013_connector_types
Revises: 012_add_liaison_public_roles
Create Date: 2026-04-16
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

from civiccore.migrations.guards import idempotent_add_column

revision: str = '013_connector_types'
down_revision: Union[str, None] = '012_liaison_public_roles'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new SourceType enum values.
    # source_type is a SHARED (CivicCore-owned) enum, but ADD VALUE IF NOT EXISTS
    # is natively idempotent — civiccore baseline can pre-declare these and the
    # statements still run cleanly here.
    op.execute("ALTER TYPE source_type ADD VALUE IF NOT EXISTS 'rest_api'")
    op.execute("ALTER TYPE source_type ADD VALUE IF NOT EXISTS 'odbc'")

    # Add last_sync_cursor column on SHARED data_sources table — guarded.
    # (last_sync_at already exists from 787207afc66a.)
    idempotent_add_column(
        "data_sources",
        sa.Column("last_sync_cursor", sa.String(), nullable=True),
    )


def downgrade() -> None:
    # Drop last_sync_cursor — this is reversible
    op.drop_column("data_sources", "last_sync_cursor")
    # PostgreSQL enum values cannot be removed — downgrade for enum additions is a no-op
    # See: https://www.postgresql.org/docs/current/sql-altertype.html
