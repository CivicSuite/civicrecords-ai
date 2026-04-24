"""Initial schema: users, service_accounts, audit_log

Revision ID: 001
Revises:
Create Date: 2026-04-11
"""
from typing import Sequence, Union

import fastapi_users_db_sqlalchemy
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from civiccore.migrations.guards import (
    idempotent_create_index,
    idempotent_create_table,
)

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Users table (fastapi-users compatible)
    # The Enum with create_type=True on the first table creates the user_role type
    idempotent_create_table(
        "users",
        sa.Column("id", fastapi_users_db_sqlalchemy.generics.GUID(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=1024), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("full_name", sa.String(), nullable=False, server_default=""),
        sa.Column("role", sa.Enum("admin", "staff", "reviewer", "read_only", name="user_role", create_type=True), nullable=False, server_default="staff"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    idempotent_create_index("ix_users_email", "users", ["email"], unique=True)

    # Service accounts table
    idempotent_create_table(
        "service_accounts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("api_key_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.Enum("admin", "staff", "reviewer", "read_only", name="user_role", create_type=False), nullable=False, server_default="read_only"),
        sa.Column("created_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # Audit log table (append-only, hash-chained)
    idempotent_create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("prev_hash", sa.String(64), nullable=False, server_default="0" * 64),
        sa.Column("entry_hash", sa.String(64), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_id", sa.String(255), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("ai_generated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.PrimaryKeyConstraint("id"),
    )
    idempotent_create_index("ix_audit_log_entry_hash", "audit_log", ["entry_hash"])
    idempotent_create_index("ix_audit_log_timestamp", "audit_log", ["timestamp"])
    idempotent_create_index("ix_audit_log_action", "audit_log", ["action"])
    idempotent_create_index("ix_audit_log_resource_type", "audit_log", ["resource_type"])
    idempotent_create_index("ix_audit_log_user_id", "audit_log", ["user_id"])
    idempotent_create_index("ix_audit_log_user_timestamp", "audit_log", ["user_id", "timestamp"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("service_accounts")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS user_role")
    op.execute("DROP EXTENSION IF EXISTS vector")
