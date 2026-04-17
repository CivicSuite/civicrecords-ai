"""Add last_sync_cursor and REST_API/ODBC source types

Revision ID: 013_connector_types
Revises: 012_add_liaison_public_roles
Create Date: 2026-04-16
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = '013_connector_types'
down_revision: Union[str, None] = '012_liaison_public_roles'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new SourceType enum values
    # PostgreSQL requires ALTER TYPE ... ADD VALUE; cannot be done inside a transaction.
    op.execute("ALTER TYPE source_type ADD VALUE IF NOT EXISTS 'rest_api'")
    op.execute("ALTER TYPE source_type ADD VALUE IF NOT EXISTS 'odbc'")

    # Add last_sync_cursor column (last_sync_at already exists)
    op.add_column(
        "data_sources",
        sa.Column("last_sync_cursor", sa.String(), nullable=True),
    )


def downgrade() -> None:
    # Drop last_sync_cursor — this is reversible
    op.drop_column("data_sources", "last_sync_cursor")
    # PostgreSQL enum values cannot be removed — downgrade for enum additions is a no-op
    # See: https://www.postgresql.org/docs/current/sql-altertype.html
