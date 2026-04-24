# backend/alembic/versions/016_p7_sync_failures.py
"""P7: sync_failures table, sync_run_log table, DataSource failure-tracking columns

Revision ID: 016_p7_sync_failures
Revises: 015_p6b_scheduler
Create Date: 2026-04-16
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from civiccore.migrations.guards import idempotent_create_table

revision: str = '016_p7_sync_failures'
down_revision: Union[str, None] = '015_p6b_scheduler'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. sync_failures table (SHARED — guarded)
    idempotent_create_table(
        "sync_failures",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_class", sa.String(200), nullable=True),
        sa.Column("http_status_code", sa.Integer(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="retrying"),
        sa.Column("first_failed_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("last_retried_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_by", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=True),
    )
    # Indexes on SHARED sync_failures — baseline may have already created
    # these. Use IF NOT EXISTS for native idempotency.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sync_failures_source_status "
        "ON sync_failures (source_id, status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sync_failures_created "
        "ON sync_failures (first_failed_at)"
    )

    # 2. sync_run_log table (SHARED — guarded)
    idempotent_create_table(
        "sync_run_log",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("records_attempted", sa.Integer(), server_default="0"),
        sa.Column("records_succeeded", sa.Integer(), server_default="0"),
        sa.Column("records_failed", sa.Integer(), server_default="0"),
        sa.Column("error_summary", sa.Text(), nullable=True),
    )
    # Index on SHARED sync_run_log — IF NOT EXISTS for baseline coexistence.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sync_run_log_source "
        "ON sync_run_log (source_id, started_at)"
    )

    # NOTE: The eight DataSource tracking columns (consecutive_failure_count, sync_paused, etc.)
    # are added by migration 015 (P6b) as nullable stubs. They MUST NOT be re-added here.
    # Migration 016 only creates the two new tables above.


def downgrade() -> None:
    op.drop_table("sync_run_log")
    op.drop_table("sync_failures")
