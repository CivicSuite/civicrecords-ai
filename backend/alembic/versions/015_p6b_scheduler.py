"""P6b: schedule_enabled, schedule_minutes -> sync_schedule conversion, drop schedule_minutes

Revision ID: 015_p6b_scheduler
Revises: 014_p6a_idempotency
Create Date: 2026-04-16

NOTE: As of 2026-04-16, no production rows have schedule_minutes set
(the UI never exposed this field). The conversion loop will process 0 rows
in a clean deployment. Verify before running on any deployment with schedule_minutes data.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

from civiccore.migrations.guards import (
    has_table,
    idempotent_add_column,
)

revision: str = '015_p6b_scheduler'
down_revision: Union[str, None] = '014_p6a_idempotency'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ALLOWLIST = {
    5:    "*/5 * * * *",
    10:   "*/10 * * * *",
    15:   "*/15 * * * *",
    20:   "*/20 * * * *",
    30:   "*/30 * * * *",
    60:   "0 * * * *",
    120:  "0 */2 * * *",
    180:  "0 */3 * * *",
    240:  "0 */4 * * *",
    360:  "0 */6 * * *",
    480:  "0 */8 * * *",
    720:  "0 */12 * * *",
    1440: "0 2 * * *",
}


def upgrade() -> None:
    conn = op.get_bind()

    # SHARED data_sources column — guarded.
    idempotent_add_column(
        "data_sources",
        sa.Column("schedule_enabled", sa.Boolean(), nullable=False, server_default="true"),
    )

    # check_constraint targets shared data_sources. Postgres lacks
    # `ADD CONSTRAINT IF NOT EXISTS` for CHECK, so use a DO block that
    # checks pg_constraint first. Idempotent on fresh installs (baseline
    # doesn't add this) and on re-runs.
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS ("
        "  SELECT 1 FROM pg_constraint WHERE conname = 'chk_sync_schedule_nonempty'"
        ") THEN "
        "  ALTER TABLE data_sources ADD CONSTRAINT chk_sync_schedule_nonempty "
        "  CHECK (sync_schedule IS NULL OR length(trim(sync_schedule)) > 0); "
        "END IF; END $$;"
    )

    # Records-only transient workspace table — leave unguarded per parent spec.
    op.create_table(
        "_migration_015_report",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.String(36), nullable=False),
        sa.Column("source_name", sa.String(255)),
        sa.Column("schedule_minutes", sa.Integer()),
        sa.Column("action", sa.String(20)),
        sa.Column("cron_expression", sa.String(50), nullable=True),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Data migration: convert legacy schedule_minutes to cron sync_schedule.
    # On a fresh install (civiccore baseline created data_sources WITHOUT the
    # legacy schedule_minutes column, since baseline reflects records HEAD
    # state where 015 already dropped it), the column does not exist and the
    # SELECT would raise. Gate the entire conversion on column presence.
    insp = inspect(conn)
    has_legacy_col = (
        has_table("data_sources")
        and "schedule_minutes" in {c["name"] for c in insp.get_columns("data_sources")}
    )
    rows = (
        conn.execute(
            text("SELECT id, name, schedule_minutes FROM data_sources WHERE schedule_minutes IS NOT NULL")
        ).fetchall()
        if has_legacy_col
        else []
    )

    for row in rows:
        source_id, name, minutes = str(row[0]), row[1], row[2]
        if minutes in _ALLOWLIST:
            cron = _ALLOWLIST[minutes]
            conn.execute(
                text("UPDATE data_sources SET sync_schedule = :cron WHERE id = :id"),
                {"cron": cron, "id": source_id},
            )
            conn.execute(
                text("""INSERT INTO _migration_015_report
                         (source_id, source_name, schedule_minutes, action, cron_expression, note)
                         VALUES (:sid, :name, :min, 'converted', :cron, 'Clean conversion')"""),
                {"sid": source_id, "name": name, "min": minutes, "cron": cron},
            )
            print(
                f"MIGRATION REPORT: Source {source_id} ('{name}'): "
                f"schedule_minutes={minutes} -> sync_schedule='{cron}'"
            )
        else:
            conn.execute(
                text("""UPDATE data_sources
                         SET sync_schedule = NULL, schedule_enabled = false
                         WHERE id = :id"""),
                {"id": source_id},
            )
            note = (
                f"schedule_minutes={minutes} has no clean cron equivalent. "
                f"Example: */45 fires at :00 and :45 only (15-min gap at hour boundary). "
                f"Admin action required: set a schedule manually in DataSources UI."
            )
            conn.execute(
                text("""INSERT INTO _migration_015_report
                         (source_id, source_name, schedule_minutes, action, cron_expression, note)
                         VALUES (:sid, :name, :min, 'nulled', NULL, :note)"""),
                {"sid": source_id, "name": name, "min": minutes, "note": note},
            )
            print(
                f"MIGRATION REPORT: Source {source_id} ('{name}'): "
                f"schedule_minutes={minutes} has no clean cron equivalent. "
                f"sync_schedule set to NULL, schedule_enabled set to False. "
                f"Admin action required."
            )

    # SHARED data_sources column drop — guarded with IF EXISTS so a fresh
    # install (where baseline never created this legacy column) succeeds.
    op.execute("ALTER TABLE data_sources DROP COLUMN IF EXISTS schedule_minutes")

    # SHARED data_sources columns — each guarded.
    for col_def in [
        sa.Column("consecutive_failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_message", sa.String(500), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_paused", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("sync_paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_paused_reason", sa.String(200), nullable=True),
        sa.Column("retry_batch_size", sa.Integer(), nullable=True),
        sa.Column("retry_time_limit_seconds", sa.Integer(), nullable=True),
    ]:
        idempotent_add_column("data_sources", col_def)


def downgrade() -> None:
    for col in [
        "retry_time_limit_seconds", "retry_batch_size", "sync_paused_reason",
        "sync_paused_at", "sync_paused", "last_error_at", "last_error_message",
        "consecutive_failure_count",
    ]:
        op.drop_column("data_sources", col)
    op.add_column(
        "data_sources",
        sa.Column("schedule_minutes", sa.Integer(), nullable=True),
    )
    op.drop_table("_migration_015_report")
    op.drop_constraint("chk_sync_schedule_nonempty", "data_sources", type_="check")
    op.drop_column("data_sources", "schedule_enabled")
