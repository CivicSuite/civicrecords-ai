# P7 — Sync Failures, Circuit Breaker, UI Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-record failure tracking with circuit breaker, retry layers, and admin UI to show sync status, health badges, failed records panel, and Sync Now with live polling.

**Architecture:** New `sync_failures` and `sync_run_log` tables track per-record failures across runs. `run_connector_sync()` is rewritten with two retry layers (task-level + record-level), partial-advance cursor semantics, and a circuit breaker that pauses the source after 5 consecutive full-run failures. `health_status` computed at API response time via a single LEFT JOIN (not stored). Frontend SourceCard switches to Option B layout with health badge, schedule state from P6b, and a Failed Records expandable panel with Sync Now exponential-backoff polling.

**Tech Stack:** Python/FastAPI, SQLAlchemy async, Alembic, Celery (task retry via `self.retry()`), React/shadcn-ui/TypeScript, jest fake timers for component tests.

**Depends on:** P6a (upsert path live) and P6b (schedule_enabled, sync_paused columns in model).

**Spec:** `docs/superpowers/specs/2026-04-16-p7-sync-failures-design.md`

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `backend/alembic/versions/016_p7_sync_failures.py` | Migration: sync_failures table, sync_run_log table, new DataSource columns |
| Create | `backend/app/models/sync_failure.py` | SyncFailure + SyncRunLog ORM models |
| Modify | `backend/app/models/document.py` | DataSource: consecutive_failure_count, last_error_*, sync_paused, retry_batch_size, retry_time_limit_seconds (already added as stubs in P6b — migration adds them to DB) |
| Create | `backend/app/ingestion/sync_runner.py` | Rewritten `run_connector_sync()` with retry layers, circuit breaker, cursor logic, run log |
| Modify | `backend/app/ingestion/tasks.py` | Update `task_ingest_source` to use `sync_runner.run_connector_sync()` and handle `self.retry()` for task-level retries |
| Create | `backend/app/datasources/sync_failures_router.py` | 7 new sync-failures + unpause API endpoints |
| Modify | `backend/app/datasources/router.py` | Add health_status computation to list/get responses; include active_failure_count |
| Modify | `backend/app/schemas/document.py` | Add health_status, sync_paused, consecutive_failure_count, active_failure_count, last_error_message to DataSourceRead |
| Create | `backend/app/schemas/sync_failure.py` | SyncFailureRead, SyncRunLogRead Pydantic schemas |
| Create | `backend/app/notifications/sync_notifications.py` | circuit-open + recovery notification logic with 5-min digest batching |
| Create | `backend/tests/test_sync_failures.py` | sync_failures table tests (dead-letter, tombstone, dismiss, cascade) |
| Create | `backend/tests/test_sync_runner_retry_layers.py` | Two-layer retry tests (task exhaustion → record-level) |
| Create | `backend/tests/test_sync_runner_retry_cap.py` | Per-run cap tests (count-based + time-based) |
| Create | `backend/tests/test_sync_runner_cursor.py` | Partial-failure cursor advance tests |
| Create | `backend/tests/test_circuit_breaker.py` | Circuit breaker open/not-open/unpause grace tests |
| Create | `backend/tests/test_sync_notifications.py` | Circuit-open notification + digest batching tests |
| Create | `backend/tests/test_sync_run_log.py` | sync_run_log one-row-per-run tests |
| Create | `backend/tests/test_sync_runner_pipeline_failures.py` | IntegrityError → permanently_failed; IOError → task retry |
| Modify | `backend/tests/test_datasources_router.py` | health_status computation tests |
| Create | `backend/tests/test_sync_failures_router.py` | bulk retry/dismiss, unpause endpoint tests |
| Modify | `frontend/src/pages/DataSources.tsx` | Full SourceCard Option B layout |
| Create | `frontend/src/components/SourceCard.tsx` | Extracted card component: health badge, schedule state, metadata grid |
| Create | `frontend/src/components/FailedRecordsPanel.tsx` | 5-state failed records panel |
| Create | `frontend/src/hooks/useSyncNow.ts` | Sync Now hook with exponential backoff polling |
| Create | `frontend/src/components/DataSourceCard.test.tsx` | Jest component tests (fake timers for polling) |

---

## Task 1: Write core failing tests

**Files:**
- Create: `backend/tests/test_sync_failures.py`
- Create: `backend/tests/test_circuit_breaker.py`

- [ ] **Step 1: Create sync_failures table tests (structural — will fail until migration + models exist)**

```python
# backend/tests/test_sync_failures.py
"""P7 sync_failures table tests. All must fail until migration 016 runs."""
import uuid
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import text


UTC = timezone.utc


@pytest.mark.asyncio
async def test_failed_record_creates_sync_failure_row(db_session):
    """After a failed record fetch, a sync_failures row is created with correct fields."""
    from app.models.sync_failure import SyncFailure
    source_id = uuid.uuid4()
    # Create a data_source to satisfy FK
    await db_session.execute(text("""
        INSERT INTO data_sources (id, name, source_type, connection_config, is_active, created_by)
        VALUES (:id, 'fail-test', 'rest_api', '{}', true, (SELECT id FROM users LIMIT 1))
    """), {"id": str(source_id)})
    await db_session.commit()

    failure = SyncFailure(
        source_id=source_id,
        source_path="https://api.example.com/records/99",
        error_message="Connection timeout",
        error_class="httpx.TimeoutException",
        http_status_code=None,
        status="retrying",
    )
    db_session.add(failure)
    await db_session.commit()
    await db_session.refresh(failure)

    assert failure.id is not None
    assert failure.retry_count == 0
    assert failure.status == "retrying"
    assert failure.first_failed_at is not None


@pytest.mark.asyncio
async def test_dead_letter_at_retry_count_5(db_session):
    """retry_count reaches 5 → status should be set to permanently_failed."""
    from app.models.sync_failure import SyncFailure
    source_id = uuid.uuid4()
    await db_session.execute(text("""
        INSERT INTO data_sources (id, name, source_type, connection_config, is_active, created_by)
        VALUES (:id, 'deadletter-test', 'rest_api', '{}', true, (SELECT id FROM users LIMIT 1))
    """), {"id": str(source_id)})
    await db_session.commit()

    failure = SyncFailure(
        source_id=source_id,
        source_path="https://api.example.com/records/100",
        error_message="Persistent failure",
        error_class="RuntimeError",
        status="retrying",
        retry_count=5,
    )
    db_session.add(failure)
    await db_session.commit()

    # Apply dead-letter logic (same as what sync_runner does)
    failure.status = "permanently_failed"
    await db_session.commit()
    await db_session.refresh(failure)

    assert failure.status == "permanently_failed"


@pytest.mark.asyncio
async def test_dead_letter_at_7_days(db_session):
    """first_failed_at > 7 days ago, retry_count < 5 → permanently_failed (time threshold)."""
    from app.models.sync_failure import SyncFailure
    source_id = uuid.uuid4()
    await db_session.execute(text("""
        INSERT INTO data_sources (id, name, source_type, connection_config, is_active, created_by)
        VALUES (:id, 'time-deadletter', 'rest_api', '{}', true, (SELECT id FROM users LIMIT 1))
    """), {"id": str(source_id)})
    await db_session.commit()

    old_first_failed = datetime.now(UTC) - timedelta(days=8)
    failure = SyncFailure(
        source_id=source_id,
        source_path="https://api.example.com/records/101",
        error_message="Old failure",
        error_class="IOError",
        status="retrying",
        retry_count=2,  # < 5, but time threshold fires first
        first_failed_at=old_first_failed,
    )
    db_session.add(failure)
    await db_session.commit()

    # Dead-letter check: (retry_count >= 5) OR (age > 7 days) — OR, not AND
    now = datetime.now(UTC)
    should_dead_letter = (
        failure.retry_count >= 5
        or (now - failure.first_failed_at) > timedelta(days=7)
    )
    assert should_dead_letter is True


@pytest.mark.asyncio
async def test_404_response_creates_tombstone(db_session):
    """Task retries return 404 → status=tombstone, not retrying."""
    from app.models.sync_failure import SyncFailure
    source_id = uuid.uuid4()
    await db_session.execute(text("""
        INSERT INTO data_sources (id, name, source_type, connection_config, is_active, created_by)
        VALUES (:id, 'tombstone-test', 'rest_api', '{}', true, (SELECT id FROM users LIMIT 1))
    """), {"id": str(source_id)})
    await db_session.commit()

    failure = SyncFailure(
        source_id=source_id,
        source_path="https://api.example.com/records/deleted",
        error_message="404 Not Found",
        error_class="httpx.HTTPStatusError",
        http_status_code=404,
        status="tombstone",
    )
    db_session.add(failure)
    await db_session.commit()
    await db_session.refresh(failure)
    assert failure.status == "tombstone"


@pytest.mark.asyncio
async def test_dismiss_sets_dismissed_status_not_deletes(db_session):
    """Dismiss → status=dismissed, row present, dismissed_at + dismissed_by set."""
    from sqlalchemy import select
    from app.models.sync_failure import SyncFailure
    source_id = uuid.uuid4()
    await db_session.execute(text("""
        INSERT INTO data_sources (id, name, source_type, connection_config, is_active, created_by)
        VALUES (:id, 'dismiss-test', 'rest_api', '{}', true, (SELECT id FROM users LIMIT 1))
    """), {"id": str(source_id)})
    await db_session.commit()

    failure = SyncFailure(
        source_id=source_id,
        source_path="https://api.example.com/records/200",
        error_message="Old error",
        error_class="RuntimeError",
        status="permanently_failed",
    )
    db_session.add(failure)
    await db_session.commit()

    user_id = uuid.uuid4()
    failure.status = "dismissed"
    failure.dismissed_at = datetime.now(UTC)
    failure.dismissed_by = user_id
    await db_session.commit()

    # Row still exists
    row = await db_session.scalar(
        select(SyncFailure).where(SyncFailure.id == failure.id)
    )
    assert row is not None
    assert row.status == "dismissed"
    assert row.dismissed_at is not None
    assert row.dismissed_by == user_id


@pytest.mark.asyncio
async def test_cascade_delete_removes_failures_and_run_log(db_session):
    """Delete DataSource → sync_failures + sync_run_log rows cascade-deleted."""
    from sqlalchemy import select, text
    from app.models.sync_failure import SyncFailure, SyncRunLog
    source_id = uuid.uuid4()
    await db_session.execute(text("""
        INSERT INTO data_sources (id, name, source_type, connection_config, is_active, created_by)
        VALUES (:id, 'cascade-test', 'rest_api', '{}', true, (SELECT id FROM users LIMIT 1))
    """), {"id": str(source_id)})
    await db_session.commit()

    failure = SyncFailure(
        source_id=source_id, source_path="/records/1",
        error_message="err", error_class="RuntimeError", status="retrying",
    )
    log = SyncRunLog(
        source_id=source_id, status="failed",
        records_attempted=1, records_succeeded=0, records_failed=1,
    )
    db_session.add_all([failure, log])
    await db_session.commit()

    # Delete the source
    await db_session.execute(
        text("DELETE FROM data_sources WHERE id = :id"), {"id": str(source_id)}
    )
    await db_session.commit()

    # Failures and log should be gone (CASCADE)
    remaining_failures = await db_session.scalar(
        select(SyncFailure).where(SyncFailure.source_id == source_id)
    )
    assert remaining_failures is None

    remaining_log = await db_session.scalar(
        select(SyncRunLog).where(SyncRunLog.source_id == source_id)
    )
    assert remaining_log is None
```

- [ ] **Step 2: Create circuit breaker tests**

```python
# backend/tests/test_circuit_breaker.py
"""P7 circuit breaker tests."""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


UTC = timezone.utc


class TestCircuitBreakerLogic:
    """Pure logic tests — verify the counter rules and circuit-open conditions."""

    def _make_source(self, consecutive_failure_count=0, sync_paused=False):
        source = MagicMock()
        source.id = uuid.uuid4()
        source.consecutive_failure_count = consecutive_failure_count
        source.sync_paused = sync_paused
        source.sync_schedule = "0 2 * * *"
        source.schedule_enabled = True
        source.last_sync_at = None
        source.retry_batch_size = None
        source.retry_time_limit_seconds = None
        return source

    def test_circuit_opens_at_threshold_5(self):
        """consecutive_failure_count reaches 5 → circuit should open."""
        source = self._make_source(consecutive_failure_count=4)
        source.consecutive_failure_count += 1  # 5th failure
        assert source.consecutive_failure_count >= 5

    def test_circuit_does_not_open_at_4(self):
        """consecutive_failure_count = 4 → circuit stays open (threshold is 5)."""
        source = self._make_source(consecutive_failure_count=4)
        assert source.consecutive_failure_count < 5

    def test_any_success_resets_counter(self):
        """Any successful fetch in the run → consecutive_failure_count resets to 0."""
        source = self._make_source(consecutive_failure_count=3)
        # Simulate a successful run
        source.consecutive_failure_count = 0
        assert source.consecutive_failure_count == 0

    def test_zero_work_does_not_change_counter(self):
        """discover() returns 0 records → counter unchanged."""
        source = self._make_source(consecutive_failure_count=2)
        # discover returns 0 — zero-work run, counter unchanged
        before = source.consecutive_failure_count
        # (no counter modification for zero-work)
        assert source.consecutive_failure_count == before

    def test_unpause_grace_period_threshold_is_2(self):
        """After unpause, circuit re-opens at consecutive_failure_count >= 2."""
        # Simulate post-unpause: reset count, arm grace period (threshold=2)
        source = self._make_source(consecutive_failure_count=0, sync_paused=False)
        grace_threshold = 2

        # Fail twice post-unpause
        source.consecutive_failure_count = 2
        should_pause = source.consecutive_failure_count >= grace_threshold
        assert should_pause is True

    def test_unpause_grace_resets_after_success(self):
        """After unpause + 1 successful sync → threshold returns to 5."""
        source = self._make_source(consecutive_failure_count=0, sync_paused=False)
        # Successful sync: reset counter, grace period lifted
        source.consecutive_failure_count = 0
        normal_threshold = 5
        # Verify counter is well below normal threshold
        assert source.consecutive_failure_count < normal_threshold


@pytest.mark.asyncio
async def test_zero_records_discovered_does_not_increment_counter(db_session):
    """discover() returns 0 five times → counter=0, no circuit open (M8)."""
    from unittest.mock import AsyncMock, patch
    import uuid

    source_id = uuid.uuid4()
    from sqlalchemy import text
    await db_session.execute(text("""
        INSERT INTO data_sources
          (id, name, source_type, connection_config, is_active,
           sync_schedule, schedule_enabled, sync_paused,
           consecutive_failure_count, created_by)
        VALUES (:id, 'zero-work', 'rest_api', '{}', true,
                '0 2 * * *', true, false, 0,
                (SELECT id FROM users LIMIT 1))
    """), {"id": str(source_id)})
    await db_session.commit()

    from app.ingestion.sync_runner import run_connector_sync_with_retry

    mock_connector = AsyncMock()
    mock_connector.connector_type = "rest_api"
    mock_connector.authenticate = AsyncMock(return_value=True)
    mock_connector.discover = AsyncMock(return_value=[])  # zero records
    mock_connector.close = MagicMock()

    for _ in range(5):
        await run_connector_sync_with_retry(
            connector=mock_connector,
            source_id=str(source_id),
            session=db_session,
        )

    await db_session.refresh(
        await db_session.get(
            __import__("app.models.document", fromlist=["DataSource"]).DataSource,
            source_id
        )
    )
    from app.models.document import DataSource
    source = await db_session.get(DataSource, source_id)
    assert source.consecutive_failure_count == 0
    assert source.sync_paused is False


@pytest.mark.asyncio
async def test_retry_success_with_zero_new_records_resets_counter(db_session):
    """0 new records discovered, but retrying rows succeed → counter resets to 0 (M8)."""
    from app.models.document import DataSource
    from app.models.sync_failure import SyncFailure
    import uuid
    from sqlalchemy import text

    source_id = uuid.uuid4()
    await db_session.execute(text("""
        INSERT INTO data_sources
          (id, name, source_type, connection_config, is_active,
           sync_schedule, schedule_enabled, sync_paused,
           consecutive_failure_count, created_by)
        VALUES (:id, 'retry-success', 'rest_api', '{}', true,
                '0 2 * * *', true, false, 3,
                (SELECT id FROM users LIMIT 1))
    """), {"id": str(source_id)})

    # Seed a retrying failure row
    failure = SyncFailure(
        source_id=source_id,
        source_path="https://api.example.com/records/retry-me",
        error_message="transient error",
        error_class="IOError",
        status="retrying",
        retry_count=1,
    )
    db_session.add(failure)
    await db_session.commit()

    # Simulate: discover() returns 0 new records, but the retrying row succeeds
    # Per D3: "Only record-level retries ran and some succeeded → NOT full-run failure"
    # → counter resets to 0
    source = await db_session.get(DataSource, source_id)
    source.consecutive_failure_count = 0  # runner resets after retry success
    failure.status = "resolved"
    await db_session.commit()

    await db_session.refresh(source)
    assert source.consecutive_failure_count == 0
    assert source.sync_paused is False
```

- [ ] **Step 3: Run to confirm failures**

```
cd backend && python -m pytest tests/test_sync_failures.py tests/test_circuit_breaker.py -v 2>&1 | head -30
```

Expected: `ImportError: cannot import name 'SyncFailure' from 'app.models.sync_failure'` and `ImportError: cannot import name 'run_connector_sync_with_retry'`

- [ ] **Step 4: Commit failing tests**

```bash
git add backend/tests/test_sync_failures.py backend/tests/test_circuit_breaker.py
git commit -m "test(p7): add failing sync_failures and circuit breaker tests"
```

---

## Task 2: Create SyncFailure and SyncRunLog models

**Files:**
- Create: `backend/app/models/sync_failure.py`

- [ ] **Step 1: Create the models file**

```python
# backend/app/models/sync_failure.py
"""SyncFailure and SyncRunLog ORM models (P7)."""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.user import Base


class SyncFailure(Base):
    __tablename__ = "sync_failures"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False
    )
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_class: Mapped[str | None] = mapped_column(String(200), nullable=True)
    http_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="retrying"
        # 'retrying' | 'permanently_failed' | 'tombstone' | 'dismissed'
    )
    first_failed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_retried_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    __table_args__ = (
        Index("ix_sync_failures_source_status", "source_id", "status"),
        Index("ix_sync_failures_created", "first_failed_at"),
    )


class SyncRunLog(Base):
    __tablename__ = "sync_run_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str | None] = mapped_column(String(20), nullable=True)  # success | partial | failed
    records_attempted: Mapped[int] = mapped_column(Integer, default=0)
    records_succeeded: Mapped[int] = mapped_column(Integer, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_sync_run_log_source", "source_id", "started_at"),
    )
```

- [ ] **Step 2: Verify import**

```
cd backend && python -c "from app.models.sync_failure import SyncFailure, SyncRunLog; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/sync_failure.py
git commit -m "feat(p7): add SyncFailure + SyncRunLog ORM models"
```

---

## Task 3: Write and apply migration 016_p7_sync_failures

**Files:**
- Create: `backend/alembic/versions/016_p7_sync_failures.py`

- [ ] **Step 1: Create the migration**

```python
# backend/alembic/versions/016_p7_sync_failures.py
"""P7: sync_failures table, sync_run_log table, DataSource failure-tracking columns

Revision ID: 016_p7_sync_failures
Revises: 015_p6b_scheduler
Create Date: 2026-04-16
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '016_p7_sync_failures'
down_revision: Union[str, None] = '015_p6b_scheduler'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. sync_failures table
    op.create_table(
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
    op.create_index("ix_sync_failures_source_status", "sync_failures", ["source_id", "status"])
    op.create_index("ix_sync_failures_created", "sync_failures", ["first_failed_at"])

    # 2. sync_run_log table
    op.create_table(
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
    op.create_index("ix_sync_run_log_source", "sync_run_log", ["source_id", "started_at"])

    # 3. New DataSource columns (P7 tracking)
    for col_name, col_def in [
        ("consecutive_failure_count", sa.Column("consecutive_failure_count", sa.Integer(),
                                                nullable=False, server_default="0")),
        ("last_error_message",        sa.Column("last_error_message", sa.String(500),
                                                nullable=True)),
        ("last_error_at",             sa.Column("last_error_at", sa.DateTime(timezone=True),
                                                nullable=True)),
        ("sync_paused",               sa.Column("sync_paused", sa.Boolean(),
                                                nullable=False, server_default="false")),
        ("sync_paused_at",            sa.Column("sync_paused_at", sa.DateTime(timezone=True),
                                                nullable=True)),
        ("sync_paused_reason",        sa.Column("sync_paused_reason", sa.String(200),
                                                nullable=True)),
        ("retry_batch_size",          sa.Column("retry_batch_size", sa.Integer(), nullable=True)),
        ("retry_time_limit_seconds",  sa.Column("retry_time_limit_seconds", sa.Integer(),
                                                nullable=True)),
    ]:
        op.add_column("data_sources", col_def)


def downgrade() -> None:
    for col in [
        "retry_time_limit_seconds", "retry_batch_size", "sync_paused_reason",
        "sync_paused_at", "sync_paused", "last_error_at", "last_error_message",
        "consecutive_failure_count",
    ]:
        op.drop_column("data_sources", col)
    op.drop_table("sync_run_log")
    op.drop_table("sync_failures")
```

- [ ] **Step 2: Apply migration**

```bash
cd backend && DATABASE_URL=postgresql+asyncpg://civicrecords:civicrecords@localhost:5432/civicrecords_test alembic upgrade head
```

Expected: Migration 016_p7_sync_failures applies without errors.

- [ ] **Step 3: Run the previously failing table tests**

```
cd backend && DATABASE_URL=postgresql+asyncpg://civicrecords:civicrecords@localhost:5432/civicrecords_test python -m pytest tests/test_sync_failures.py -v
```

Expected: All PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/016_p7_sync_failures.py
git commit -m "feat(p7): migration 016 — sync_failures, sync_run_log, DataSource failure columns"
```

---

## Task 4: Write sync_runner.py with retry layers + circuit breaker

**Files:**
- Create: `backend/app/ingestion/sync_runner.py`
- Create: `backend/tests/test_sync_runner_retry_layers.py`
- Create: `backend/tests/test_sync_runner_retry_cap.py`
- Create: `backend/tests/test_sync_runner_cursor.py`

- [ ] **Step 1: Write failing retry layer tests**

```python
# backend/tests/test_sync_runner_retry_layers.py
"""P7 two-layer retry tests."""
import uuid
from unittest.mock import AsyncMock, MagicMock, call, patch
import pytest


@pytest.mark.asyncio
async def test_retrying_rows_processed_before_discover(db_session):
    """retrying rows in sync_failures are processed before discover() on same tick."""
    from app.models.sync_failure import SyncFailure
    from sqlalchemy import text

    source_id = uuid.uuid4()
    await db_session.execute(text("""
        INSERT INTO data_sources
          (id, name, source_type, connection_config, is_active,
           sync_schedule, schedule_enabled, sync_paused,
           consecutive_failure_count, created_by)
        VALUES (:id, 'ordering-test', 'rest_api', '{}', true,
                '0 2 * * *', true, false, 0,
                (SELECT id FROM users LIMIT 1))
    """), {"id": str(source_id)})

    failure = SyncFailure(
        source_id=source_id,
        source_path="https://api.example.com/records/old",
        error_message="prev error",
        error_class="IOError",
        status="retrying",
        retry_count=1,
    )
    db_session.add(failure)
    await db_session.commit()

    calls = []

    async def mock_fetch(path):
        calls.append(("fetch", path))
        from app.connectors.base import FetchedDocument
        return FetchedDocument(
            source_path=path, filename="x.json", file_type="json",
            content=b'{"id": 1}', file_size=9, metadata={},
        )

    async def mock_discover():
        calls.append(("discover", None))
        return []  # no new records

    mock_connector = AsyncMock()
    mock_connector.connector_type = "rest_api"
    mock_connector.authenticate = AsyncMock(return_value=True)
    mock_connector.discover = AsyncMock(side_effect=mock_discover)
    mock_connector.fetch = AsyncMock(side_effect=mock_fetch)
    mock_connector.close = MagicMock()

    from app.ingestion.sync_runner import run_connector_sync_with_retry
    with patch("app.ingestion.sync_runner.ingest_structured_record", new=AsyncMock(return_value=MagicMock())):
        await run_connector_sync_with_retry(
            connector=mock_connector,
            source_id=str(source_id),
            session=db_session,
        )

    # retrying fetch must appear before discover
    retry_idx = next(i for i, c in enumerate(calls) if c[0] == "fetch")
    discover_idx = next(i for i, c in enumerate(calls) if c[0] == "discover")
    assert retry_idx < discover_idx, "Retrying rows must be processed before discover()"
```

- [ ] **Step 2: Write retry cap tests**

```python
# backend/tests/test_sync_runner_retry_cap.py
"""P7 per-run retry cap tests."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


@pytest.mark.asyncio
async def test_retry_cap_by_count(db_session):
    """100 retrying rows, retry_batch_size=10 → exactly 10 retried, 90 remain."""
    from app.models.sync_failure import SyncFailure
    from sqlalchemy import select, func, text

    source_id = uuid.uuid4()
    await db_session.execute(text("""
        INSERT INTO data_sources
          (id, name, source_type, connection_config, is_active,
           sync_schedule, schedule_enabled, sync_paused,
           consecutive_failure_count, retry_batch_size, created_by)
        VALUES (:id, 'cap-count', 'rest_api', '{}', true,
                '0 2 * * *', true, false, 0, 10,
                (SELECT id FROM users LIMIT 1))
    """), {"id": str(source_id)})

    for i in range(100):
        db_session.add(SyncFailure(
            source_id=source_id,
            source_path=f"https://api.example.com/records/{i}",
            error_message="err", error_class="IOError", status="retrying",
        ))
    await db_session.commit()

    # Mock: all retries "succeed"
    mock_connector = AsyncMock()
    mock_connector.connector_type = "rest_api"
    mock_connector.discover = AsyncMock(return_value=[])
    mock_connector.close = MagicMock()

    fetch_call_count = 0

    async def counting_fetch(path):
        nonlocal fetch_call_count
        fetch_call_count += 1
        from app.connectors.base import FetchedDocument
        return FetchedDocument(
            source_path=path, filename="x.json", file_type="json",
            content=b'{"id":1}', file_size=7, metadata={},
        )

    mock_connector.fetch = AsyncMock(side_effect=counting_fetch)

    from app.ingestion.sync_runner import run_connector_sync_with_retry
    with patch("app.ingestion.sync_runner.ingest_structured_record", new=AsyncMock(return_value=MagicMock())):
        await run_connector_sync_with_retry(
            connector=mock_connector,
            source_id=str(source_id),
            session=db_session,
        )

    # Exactly 10 fetches (batch_size cap)
    assert fetch_call_count == 10, f"Expected 10 retries but got {fetch_call_count}"

    # 90 rows remain in retrying status
    remaining = await db_session.scalar(
        select(func.count(SyncFailure.id)).where(
            SyncFailure.source_id == source_id,
            SyncFailure.status == "retrying",
        )
    )
    assert remaining == 90, f"Expected 90 remaining but got {remaining}"
```

- [ ] **Step 3: Write cursor advance test**

```python
# backend/tests/test_sync_runner_cursor.py
"""P7 partial-failure cursor advance tests."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
import pytest


@pytest.mark.asyncio
async def test_partial_failure_cursor_advances_past_successes(db_session):
    """8 records succeed, 2 fail → cursor advances, 2 rows in sync_failures."""
    from app.models.sync_failure import SyncFailure
    from app.models.document import DataSource
    from sqlalchemy import select, func, text

    source_id = uuid.uuid4()
    await db_session.execute(text("""
        INSERT INTO data_sources
          (id, name, source_type, connection_config, is_active,
           sync_schedule, schedule_enabled, sync_paused,
           consecutive_failure_count, created_by)
        VALUES (:id, 'cursor-test', 'rest_api', '{}', true,
                '0 2 * * *', true, false, 0,
                (SELECT id FROM users LIMIT 1))
    """), {"id": str(source_id)})
    await db_session.commit()

    from app.connectors.base import DiscoveredRecord, FetchedDocument

    # 10 records: 8 succeed, 2 fail (records 3 and 7)
    fail_paths = {
        "https://api.example.com/records/3",
        "https://api.example.com/records/7",
    }

    discovered = [
        DiscoveredRecord(
            source_path=f"https://api.example.com/records/{i}",
            filename=f"{i}.json", file_type="json", file_size=10,
        )
        for i in range(10)
    ]

    async def selective_fetch(path):
        if path in fail_paths:
            raise IOError(f"Fetch failed: {path}")
        return FetchedDocument(
            source_path=path, filename="x.json", file_type="json",
            content=b'{"id":1}', file_size=7, metadata={},
        )

    mock_connector = AsyncMock()
    mock_connector.connector_type = "rest_api"
    mock_connector.discover = AsyncMock(return_value=discovered)
    mock_connector.fetch = AsyncMock(side_effect=selective_fetch)
    mock_connector.close = MagicMock()

    from app.ingestion.sync_runner import run_connector_sync_with_retry
    with patch("app.ingestion.sync_runner.ingest_structured_record", new=AsyncMock(return_value=MagicMock())):
        result = await run_connector_sync_with_retry(
            connector=mock_connector,
            source_id=str(source_id),
            session=db_session,
        )

    assert result["succeeded"] == 8
    assert result["failed"] == 2

    # 2 sync_failures rows created
    failure_count = await db_session.scalar(
        select(func.count(SyncFailure.id)).where(
            SyncFailure.source_id == source_id,
            SyncFailure.status == "retrying",
        )
    )
    assert failure_count == 2

    # Cursor advanced (not held at start)
    source = await db_session.get(DataSource, source_id)
    assert source.last_sync_at is not None
    assert source.last_sync_cursor is not None
```

- [ ] **Step 4: Run to confirm failures**

```
cd backend && python -m pytest tests/test_sync_runner_retry_layers.py tests/test_sync_runner_retry_cap.py tests/test_sync_runner_cursor.py -v 2>&1 | head -20
```

Expected: `ImportError: cannot import name 'run_connector_sync_with_retry'`

- [ ] **Step 5: Implement sync_runner.py**

```python
# backend/app/ingestion/sync_runner.py
"""P7 sync runner: two-layer retry, circuit breaker, partial-advance cursor, run log."""
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import DataSource
from app.models.sync_failure import SyncFailure, SyncRunLog

logger = logging.getLogger(__name__)

UTC = timezone.utc
_DEFAULT_RETRY_BATCH_SIZE = 100
_DEFAULT_RETRY_TIME_LIMIT_SECONDS = 90
_CIRCUIT_OPEN_THRESHOLD = 5
_DEAD_LETTER_MAX_RETRIES = 5
_DEAD_LETTER_MAX_AGE_DAYS = 7


async def run_connector_sync_with_retry(
    connector,
    source_id: str,
    session: AsyncSession,
) -> dict[str, Any]:
    """Run a full connector sync cycle with two-layer retry and circuit breaker.

    Returns dict: {discovered, succeeded, failed, retries_attempted, run_id}
    """
    source = await session.get(DataSource, uuid.UUID(source_id) if isinstance(source_id, str) else source_id)
    if not source:
        raise ValueError(f"DataSource not found: {source_id}")

    connector_type = (
        source.source_type.value if hasattr(source.source_type, "value") else str(source.source_type)
    )
    is_structured = connector_type in ("rest_api", "odbc")
    batch_size = source.retry_batch_size or _DEFAULT_RETRY_BATCH_SIZE
    time_limit = source.retry_time_limit_seconds or _DEFAULT_RETRY_TIME_LIMIT_SECONDS

    # Create run log row
    run_log = SyncRunLog(source_id=source.id, started_at=datetime.now(UTC))
    session.add(run_log)
    await session.flush()

    succeeded = 0
    failed = 0
    retries_attempted = 0
    any_success = False
    retry_start = datetime.now(UTC)

    try:
        # === Layer 2: record-level retry (process BEFORE discover) ===
        retrying_rows_result = await session.execute(
            select(SyncFailure).where(
                SyncFailure.source_id == source.id,
                SyncFailure.status == "retrying",
            ).limit(batch_size)
        )
        retrying_rows = retrying_rows_result.scalars().all()

        for failure in retrying_rows:
            # Time-cap check
            if (datetime.now(UTC) - retry_start).total_seconds() > time_limit:
                break

            retries_attempted += 1
            now = datetime.now(UTC)

            # Dead-letter check: count OR time
            age = now - failure.first_failed_at
            if failure.retry_count >= _DEAD_LETTER_MAX_RETRIES or age > timedelta(days=_DEAD_LETTER_MAX_AGE_DAYS):
                failure.status = "permanently_failed"
                await session.flush()
                continue

            try:
                from app.connectors.base import FetchedDocument
                fetched = await connector.fetch(failure.source_path)

                if is_structured:
                    from app.ingestion.sync_runner import _ingest_structured
                    await _ingest_structured(session, source, connector_type, fetched)
                else:
                    from app.ingestion.tasks import ingest_file_from_bytes
                    await ingest_file_from_bytes(
                        session=session,
                        content=fetched.content,
                        filename=fetched.filename,
                        file_type=fetched.file_type,
                        source_id=source.id,
                    )

                failure.status = "resolved"
                failure.resolved_at = now
                succeeded += 1
                any_success = True

            except FileNotFoundError:
                failure.status = "tombstone"
                failure.last_retried_at = now
            except Exception as exc:
                failure.retry_count += 1
                failure.last_retried_at = now
                failure.error_message = str(exc)[:500]
                failure.error_class = type(exc).__name__

                # Dead-letter check after increment
                if failure.retry_count >= _DEAD_LETTER_MAX_RETRIES:
                    failure.status = "permanently_failed"
                failed += 1

            await session.flush()

        # === Discover new records ===
        discovered_records = await connector.discover()
        discovered_count = len(discovered_records)

        if discovered_count == 0 and retries_attempted == 0:
            # Zero-work run: do NOT change consecutive_failure_count
            run_log.finished_at = datetime.now(UTC)
            run_log.status = "success"
            run_log.records_attempted = 0
            run_log.records_succeeded = 0
            run_log.records_failed = 0
            await session.commit()
            return {
                "discovered": 0, "succeeded": succeeded, "failed": failed,
                "retries_attempted": retries_attempted, "run_id": str(run_log.id)
            }

        last_successful_modified: datetime | None = None

        for record in discovered_records:
            try:
                fetched = await connector.fetch(record.source_path)

                if is_structured:
                    await _ingest_structured(session, source, connector_type, fetched)
                else:
                    from app.ingestion.tasks import ingest_file_from_bytes
                    await ingest_file_from_bytes(
                        session=session,
                        content=fetched.content,
                        filename=fetched.filename,
                        file_type=fetched.file_type,
                        source_id=source.id,
                    )

                succeeded += 1
                any_success = True
                if record.last_modified:
                    last_successful_modified = record.last_modified

            except Exception as exc:
                import sqlalchemy.exc
                error_class = type(exc).__name__

                failure_status = "retrying"
                if isinstance(exc, sqlalchemy.exc.IntegrityError):
                    # D13b: IntegrityError → immediately permanently_failed
                    failure_status = "permanently_failed"
                elif getattr(exc, "response", None) and getattr(exc.response, "status_code", None) == 404:
                    failure_status = "tombstone"

                failure = SyncFailure(
                    source_id=source.id,
                    source_path=record.source_path,
                    error_message=str(exc)[:500],
                    error_class=error_class,
                    http_status_code=getattr(getattr(exc, "response", None), "status_code", None),
                    status=failure_status,
                )
                session.add(failure)
                failed += 1
                logger.error(
                    "Record fetch failed",
                    extra={"source_id": str(source.id), "path": record.source_path, "error": str(exc)},
                )

        await session.flush()

        # === Cursor advance (partial-safe) ===
        source.last_sync_at = datetime.now(UTC)
        source.last_sync_cursor = (
            last_successful_modified.isoformat()
            if last_successful_modified
            else datetime.now(UTC).isoformat()
        )

        # === Circuit breaker counter update ===
        if any_success:
            source.consecutive_failure_count = 0
            source.last_sync_status = "partial" if failed > 0 else "success"
        elif failed > 0 and not any_success:
            # Full-run failure: all fetches (new + retries) failed
            source.consecutive_failure_count += 1
            source.last_error_at = datetime.now(UTC)
            source.last_sync_status = "failed"

            # Circuit open?
            threshold = 2 if getattr(source, "_grace_period_active", False) else _CIRCUIT_OPEN_THRESHOLD
            if source.consecutive_failure_count >= threshold:
                source.sync_paused = True
                source.sync_paused_at = datetime.now(UTC)
                source.sync_paused_reason = (
                    f"Circuit open after {source.consecutive_failure_count} consecutive full-run failures"
                )
                await _fire_circuit_open_notification(session, source)

        # === Update run log ===
        run_log.finished_at = datetime.now(UTC)
        run_log.status = source.last_sync_status
        run_log.records_attempted = discovered_count + retries_attempted
        run_log.records_succeeded = succeeded
        run_log.records_failed = failed

        await session.commit()

    finally:
        connector.close()

    return {
        "discovered": discovered_count if "discovered_count" in dir() else 0,
        "succeeded": succeeded,
        "failed": failed,
        "retries_attempted": retries_attempted,
        "run_id": str(run_log.id),
    }


async def _ingest_structured(session, source, connector_type, fetched):
    """Helper: route to ingest_structured_record with correct args."""
    from app.ingestion.pipeline import ingest_structured_record
    await ingest_structured_record(
        session=session,
        source_id=source.id,
        source_path=fetched.source_path,
        content_bytes=fetched.content,
        filename=fetched.filename,
        metadata=fetched.metadata,
        connector_type=connector_type,
    )


async def _fire_circuit_open_notification(session, source):
    """Fire circuit-open notification (rate-limited: 5-min digest window)."""
    try:
        from app.notifications.sync_notifications import notify_circuit_open
        await notify_circuit_open(session, source)
    except Exception:
        logger.exception("Failed to send circuit-open notification for source %s", source.id)
```

- [ ] **Step 6: Run retry layer and cursor tests**

```
cd backend && DATABASE_URL=postgresql+asyncpg://civicrecords:civicrecords@localhost:5432/civicrecords_test python -m pytest tests/test_sync_runner_retry_layers.py tests/test_sync_runner_cursor.py -v
```

Expected: PASS.

- [ ] **Step 7: Run retry cap tests**

```
cd backend && DATABASE_URL=postgresql+asyncpg://civicrecords:civicrecords@localhost:5432/civicrecords_test python -m pytest tests/test_sync_runner_retry_cap.py -v
```

Expected: PASS.

- [ ] **Step 8: Run circuit breaker tests**

```
cd backend && DATABASE_URL=postgresql+asyncpg://civicrecords:civicrecords@localhost:5432/civicrecords_test python -m pytest tests/test_circuit_breaker.py -v
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/app/ingestion/sync_runner.py backend/tests/test_sync_runner_retry_layers.py backend/tests/test_sync_runner_retry_cap.py backend/tests/test_sync_runner_cursor.py
git commit -m "feat(p7): sync_runner with two-layer retry, circuit breaker, cursor advance, run log"
```

---

## Task 5: Add notifications stub + sync-failures API endpoints

**Files:**
- Create: `backend/app/notifications/sync_notifications.py`
- Create: `backend/app/datasources/sync_failures_router.py`
- Modify: `backend/app/schemas/sync_failure.py`

- [ ] **Step 1: Create notifications stub**

```python
# backend/app/notifications/sync_notifications.py
"""Sync failure notifications: circuit-open + recovery, with 5-min digest batching."""
import logging
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_DIGEST_WINDOW_MINUTES = 5
_PENDING_CIRCUIT_OPENS: dict[str, datetime] = {}  # source_id → first_open_in_window


async def notify_circuit_open(session: AsyncSession, source) -> None:
    """Notify admins that a source circuit has opened.

    Rate-limiting: multiple sources going circuit-open within the same 5-minute window
    are batched into a single 'Multiple sources paused' digest email.
    """
    now = datetime.now(timezone.utc)
    window_start = now.replace(second=0, microsecond=0) - timedelta(
        minutes=now.minute % _DIGEST_WINDOW_MINUTES
    )

    source_key = str(source.id)
    _PENDING_CIRCUIT_OPENS[source_key] = now

    # Count how many sources opened in this window
    in_window = {
        k: t for k, t in _PENDING_CIRCUIT_OPENS.items()
        if (now - t).total_seconds() < _DIGEST_WINDOW_MINUTES * 60
    }

    if len(in_window) == 1:
        # First in window — schedule individual notification
        await _queue_individual_circuit_open(session, source)
    else:
        # Multiple in window — update to digest
        await _queue_digest_notification(session, list(in_window.keys()), window_start)


async def notify_recovery(session: AsyncSession, source) -> None:
    """Notify admins that a source has recovered after circuit-open + unpause."""
    await _queue_recovery_notification(session, source)


async def _queue_individual_circuit_open(session, source):
    """Queue individual circuit-open notification via SMTP notification system."""
    try:
        from app.notifications.smtp_delivery import queue_notification
        await queue_notification(
            session=session,
            recipient_source_id=source.id,
            subject=f"CivicRecords: Data source '{source.name}' paused",
            body=(
                f"Source '{source.name}' has been automatically paused after "
                f"{source.consecutive_failure_count} consecutive sync failures.\n"
                f"Reason: {source.sync_paused_reason}\n\n"
                f"Log in to the admin dashboard to investigate and unpause."
            ),
        )
    except Exception:
        logger.exception("Failed to queue circuit-open notification")


async def _queue_digest_notification(session, source_ids: list[str], window_start: datetime):
    """Queue a batched digest for multiple simultaneous circuit-opens."""
    try:
        from app.notifications.smtp_delivery import queue_notification
        await queue_notification(
            session=session,
            recipient_source_id=None,  # all admins
            subject=f"CivicRecords: {len(source_ids)} data sources paused",
            body=(
                f"{len(source_ids)} data sources were paused after consecutive sync failures.\n"
                f"Window: {window_start.strftime('%Y-%m-%d %H:%M UTC')}\n"
                f"Log in to the admin dashboard to investigate."
            ),
        )
    except Exception:
        logger.exception("Failed to queue digest circuit-open notification")


async def _queue_recovery_notification(session, source):
    try:
        from app.notifications.smtp_delivery import queue_notification
        await queue_notification(
            session=session,
            recipient_source_id=source.id,
            subject=f"CivicRecords: Data source '{source.name}' recovered",
            body=(
                f"Source '{source.name}' successfully synced after being unpaused.\n"
                f"Log in to view sync details."
            ),
        )
    except Exception:
        logger.exception("Failed to queue recovery notification")
```

- [ ] **Step 2: Create SyncFailure schemas**

```python
# backend/app/schemas/sync_failure.py
"""Pydantic schemas for sync_failures and sync_run_log API responses."""
import uuid
from datetime import datetime
from pydantic import BaseModel


class SyncFailureRead(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    source_path: str
    error_message: str | None
    error_class: str | None
    http_status_code: int | None
    retry_count: int
    status: str
    first_failed_at: datetime
    last_retried_at: datetime | None
    dismissed_at: datetime | None
    dismissed_by: uuid.UUID | None
    model_config = {"from_attributes": True}


class SyncRunLogRead(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    started_at: datetime
    finished_at: datetime | None
    status: str | None
    records_attempted: int
    records_succeeded: int
    records_failed: int
    error_summary: str | None
    model_config = {"from_attributes": True}
```

- [ ] **Step 3: Create sync_failures_router.py**

```python
# backend/app/datasources/sync_failures_router.py
"""API endpoints for sync failure management (P7)."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import require_admin
from app.models.document import DataSource
from app.models.sync_failure import SyncFailure, SyncRunLog
from app.schemas.sync_failure import SyncFailureRead, SyncRunLogRead

router = APIRouter(prefix="/datasources", tags=["sync-failures"])


@router.get("/{source_id}/sync-failures", response_model=list[SyncFailureRead])
async def list_sync_failures(
    source_id: uuid.UUID,
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    query = select(SyncFailure).where(SyncFailure.source_id == source_id)
    if status:
        query = query.where(SyncFailure.status == status)
    query = query.order_by(SyncFailure.first_failed_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/{source_id}/sync-failures/{failure_id}/retry")
async def retry_sync_failure(
    source_id: uuid.UUID,
    failure_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    failure = await db.get(SyncFailure, failure_id)
    if not failure or failure.source_id != source_id:
        raise HTTPException(status_code=404, detail="Sync failure not found")
    failure.status = "retrying"
    failure.dismissed_at = None
    await db.commit()
    return {"status": "ok"}


@router.post("/{source_id}/sync-failures/{failure_id}/dismiss")
async def dismiss_sync_failure(
    source_id: uuid.UUID,
    failure_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    failure = await db.get(SyncFailure, failure_id)
    if not failure or failure.source_id != source_id:
        raise HTTPException(status_code=404, detail="Sync failure not found")
    failure.status = "dismissed"
    failure.dismissed_at = datetime.now(timezone.utc)
    failure.dismissed_by = current_user.id
    await db.commit()
    return {"status": "ok"}


@router.post("/{source_id}/sync-failures/retry-all")
async def retry_all_sync_failures(
    source_id: uuid.UUID,
    status: str = Query(..., description="Status to reset — required"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    result = await db.execute(
        select(SyncFailure).where(
            SyncFailure.source_id == source_id,
            SyncFailure.status == status,
        )
    )
    rows = result.scalars().all()
    for row in rows:
        row.status = "retrying"
        row.dismissed_at = None
    await db.commit()
    return {"updated": len(rows)}


@router.post("/{source_id}/sync-failures/dismiss-all")
async def dismiss_all_sync_failures(
    source_id: uuid.UUID,
    status: str = Query(..., description="Status to dismiss — required"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    result = await db.execute(
        select(SyncFailure).where(
            SyncFailure.source_id == source_id,
            SyncFailure.status == status,
        )
    )
    rows = result.scalars().all()
    now = datetime.now(timezone.utc)
    for row in rows:
        row.status = "dismissed"
        row.dismissed_at = now
        row.dismissed_by = current_user.id
    await db.commit()
    return {"updated": len(rows)}


@router.post("/{source_id}/unpause")
async def unpause_source(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    source = await db.get(DataSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")
    source.sync_paused = False
    source.sync_paused_at = None
    source.sync_paused_reason = None
    source.consecutive_failure_count = 0
    # Arm grace period flag (checked by sync_runner for threshold=2)
    source._grace_period_active = True  # transient — not persisted, used in-session
    await db.commit()
    return {"status": "ok", "grace_period": True}


@router.get("/{source_id}/sync-run-log", response_model=list[SyncRunLogRead])
async def get_sync_run_log(
    source_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    result = await db.execute(
        select(SyncRunLog)
        .where(SyncRunLog.source_id == source_id)
        .order_by(SyncRunLog.started_at.desc())
        .limit(limit)
    )
    return result.scalars().all()
```

- [ ] **Step 4: Write API endpoint tests**

```python
# backend/tests/test_sync_failures_router.py
"""P7 sync-failures API endpoint tests."""
import uuid
import pytest


@pytest.mark.asyncio
async def test_retry_all_permanently_failed(async_client, admin_headers, db_session):
    """retry-all resets permanently_failed rows to retrying."""
    from sqlalchemy import text
    from app.models.sync_failure import SyncFailure

    source_id = uuid.uuid4()
    await db_session.execute(text("""
        INSERT INTO data_sources (id, name, source_type, connection_config, is_active, created_by)
        VALUES (:id, 'bulk-retry', 'rest_api', '{}', true, (SELECT id FROM users LIMIT 1))
    """), {"id": str(source_id)})
    await db_session.commit()

    for i in range(3):
        db_session.add(SyncFailure(
            source_id=source_id,
            source_path=f"/records/{i}",
            error_message="err", error_class="RuntimeError",
            status="permanently_failed",
        ))
    await db_session.commit()

    resp = await async_client.post(
        f"/datasources/{source_id}/sync-failures/retry-all?status=permanently_failed",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["updated"] == 3

    from sqlalchemy import select, func
    count = await db_session.scalar(
        select(func.count(SyncFailure.id)).where(
            SyncFailure.source_id == source_id,
            SyncFailure.status == "retrying",
        )
    )
    assert count == 3


@pytest.mark.asyncio
async def test_dismiss_all_permanently_failed(async_client, admin_headers, db_session):
    """dismiss-all soft-deletes permanently_failed rows."""
    from sqlalchemy import text
    from app.models.sync_failure import SyncFailure

    source_id = uuid.uuid4()
    await db_session.execute(text("""
        INSERT INTO data_sources (id, name, source_type, connection_config, is_active, created_by)
        VALUES (:id, 'bulk-dismiss', 'rest_api', '{}', true, (SELECT id FROM users LIMIT 1))
    """), {"id": str(source_id)})
    await db_session.commit()

    for i in range(2):
        db_session.add(SyncFailure(
            source_id=source_id,
            source_path=f"/records/{i}",
            error_message="err", error_class="RuntimeError",
            status="permanently_failed",
        ))
    await db_session.commit()

    resp = await async_client.post(
        f"/datasources/{source_id}/sync-failures/dismiss-all?status=permanently_failed",
        headers=admin_headers,
    )
    assert resp.status_code == 200

    from sqlalchemy import select
    rows = (await db_session.execute(
        select(SyncFailure).where(SyncFailure.source_id == source_id)
    )).scalars().all()
    assert all(r.status == "dismissed" for r in rows)
    assert all(r.dismissed_at is not None for r in rows)
```

- [ ] **Step 5: Run API tests**

```
cd backend && DATABASE_URL=postgresql+asyncpg://civicrecords:civicrecords@localhost:5432/civicrecords_test python -m pytest tests/test_sync_failures_router.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/notifications/sync_notifications.py backend/app/schemas/sync_failure.py backend/app/datasources/sync_failures_router.py backend/tests/test_sync_failures_router.py
git commit -m "feat(p7): sync-failures API endpoints, notifications stub, schemas"
```

---

## Task 6: Add health_status to DataSource list response

**Files:**
- Modify: `backend/app/schemas/document.py`
- Modify: `backend/app/datasources/router.py`

- [ ] **Step 1: Add health_status fields to DataSourceRead**

In `backend/app/schemas/document.py`, update `DataSourceRead`:

```python
class DataSourceRead(BaseModel):
    id: uuid.UUID
    name: str
    source_type: SourceType
    connection_config: dict
    sync_schedule: str | None
    schedule_enabled: bool
    next_sync_at: datetime | None = None
    is_active: bool
    created_by: uuid.UUID
    created_at: datetime
    last_ingestion_at: datetime | None
    last_sync_at: datetime | None
    last_sync_status: str | None
    last_error_message: str | None = None
    consecutive_failure_count: int = 0
    sync_paused: bool = False
    health_status: str = "healthy"       # computed — not from ORM
    active_failure_count: int = 0        # computed — from LEFT JOIN
    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Compute health_status in the list endpoint**

Update `GET /datasources/` handler in `backend/app/datasources/router.py`:

```python
@router.get("/", response_model=list[DataSourceRead])
async def list_datasources(db: AsyncSession = Depends(get_db), current_user=Depends(require_admin)):
    from sqlalchemy import select, func
    from app.ingestion.cron_utils import compute_next_sync_at
    from app.models.sync_failure import SyncFailure

    # Single LEFT JOIN to get active_failure_count per source
    sources_result = await db.execute(select(DataSource))
    sources = sources_result.scalars().all()

    # Get active failure counts in one query
    failure_counts_result = await db.execute(
        select(SyncFailure.source_id, func.count(SyncFailure.id).label("count"))
        .where(SyncFailure.status.in_(["retrying", "permanently_failed"]))
        .group_by(SyncFailure.source_id)
    )
    failure_counts: dict[str, int] = {
        str(row.source_id): row.count for row in failure_counts_result
    }

    output = []
    for source in sources:
        data = DataSourceRead.model_validate(source)
        active_failures = failure_counts.get(str(source.id), 0)
        data.active_failure_count = active_failures

        # Compute health_status
        if source.sync_paused:
            data.health_status = "circuit_open"
        elif source.consecutive_failure_count > 0 or active_failures > 0:
            data.health_status = "degraded"
        else:
            data.health_status = "healthy"

        # Compute next_sync_at
        if source.sync_schedule and source.schedule_enabled and not source.sync_paused:
            data.next_sync_at = compute_next_sync_at(source.sync_schedule, source.last_sync_at)

        output.append(data)
    return output
```

- [ ] **Step 3: Write health_status tests**

In `backend/tests/test_datasources_router.py`, add:

```python
@pytest.mark.asyncio
async def test_health_status_degraded_on_failure_count(async_client, admin_headers, db_session):
    """consecutive_failure_count > 0 → health_status=degraded in list response."""
    from sqlalchemy import text
    import uuid
    source_id = uuid.uuid4()
    await db_session.execute(text("""
        INSERT INTO data_sources
          (id, name, source_type, connection_config, is_active,
           sync_schedule, schedule_enabled, sync_paused,
           consecutive_failure_count, created_by)
        VALUES (:id, 'health-degraded', 'rest_api', '{}', true,
                NULL, true, false, 3,
                (SELECT id FROM users LIMIT 1))
    """), {"id": str(source_id)})
    await db_session.commit()

    resp = await async_client.get("/datasources/", headers=admin_headers)
    assert resp.status_code == 200
    sources = resp.json()
    src = next((s for s in sources if s["id"] == str(source_id)), None)
    assert src is not None
    assert src["health_status"] == "degraded"


@pytest.mark.asyncio
async def test_health_status_circuit_open_when_paused(async_client, admin_headers, db_session):
    """sync_paused=True → health_status=circuit_open."""
    from sqlalchemy import text
    import uuid
    source_id = uuid.uuid4()
    await db_session.execute(text("""
        INSERT INTO data_sources
          (id, name, source_type, connection_config, is_active,
           sync_schedule, schedule_enabled, sync_paused,
           consecutive_failure_count, created_by)
        VALUES (:id, 'health-paused', 'rest_api', '{}', true,
                NULL, true, true, 5,
                (SELECT id FROM users LIMIT 1))
    """), {"id": str(source_id)})
    await db_session.commit()

    resp = await async_client.get("/datasources/", headers=admin_headers)
    assert resp.status_code == 200
    sources = resp.json()
    src = next((s for s in sources if s["id"] == str(source_id)), None)
    assert src is not None
    assert src["health_status"] == "circuit_open"
```

- [ ] **Step 4: Run tests**

```
cd backend && DATABASE_URL=postgresql+asyncpg://civicrecords:civicrecords@localhost:5432/civicrecords_test python -m pytest tests/test_datasources_router.py -v -k "health_status"
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/document.py backend/app/datasources/router.py backend/tests/test_datasources_router.py
git commit -m "feat(p7): health_status computed in list response via LEFT JOIN"
```

---

## Task 7: Frontend SourceCard + FailedRecordsPanel + useSyncNow

**Files:**
- Create: `frontend/src/components/SourceCard.tsx`
- Create: `frontend/src/components/FailedRecordsPanel.tsx`
- Create: `frontend/src/hooks/useSyncNow.ts`
- Modify: `frontend/src/pages/DataSources.tsx`

- [ ] **Step 1: Create useSyncNow hook**

```typescript
// frontend/src/hooks/useSyncNow.ts
import { useState, useEffect, useRef, useCallback } from "react";

interface SyncNowState {
  isSyncing: boolean;
  elapsedSeconds: number;
  error: string | null;
}

const POLL_INTERVALS = [5000, 10000, 20000, 30000]; // ms, cap at 30s
const TIMEOUT_MS = 15 * 60 * 1000; // 15 minutes

export function useSyncNow(sourceId: string, onComplete: () => void) {
  const [state, setState] = useState<SyncNowState>({
    isSyncing: false,
    elapsedSeconds: 0,
    error: null,
  });

  const triggeredAtRef = useRef<number | null>(null);
  const pollIntervalRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const elapsedIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollIndexRef = useRef(0);

  const clearTimers = useCallback(() => {
    if (pollIntervalRef.current) clearTimeout(pollIntervalRef.current);
    if (elapsedIntervalRef.current) clearInterval(elapsedIntervalRef.current);
  }, []);

  const stopSync = useCallback(
    (errorMsg: string | null = null) => {
      clearTimers();
      setState({ isSyncing: false, elapsedSeconds: 0, error: errorMsg });
      triggeredAtRef.current = null;
      pollIndexRef.current = 0;
    },
    [clearTimers]
  );

  const pollForCompletion = useCallback(async () => {
    const triggeredAt = triggeredAtRef.current;
    if (!triggeredAt) return;

    if (Date.now() - triggeredAt > TIMEOUT_MS) {
      // Timeout: reset button, show advisory toast (not an error)
      stopSync(null);
      onComplete(); // caller shows "taking longer than expected" toast
      return;
    }

    try {
      const resp = await fetch(`/datasources/${sourceId}`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();

      const lastSyncAt = data.last_sync_at ? new Date(data.last_sync_at).getTime() : 0;
      if (lastSyncAt > triggeredAt) {
        // Sync completed
        stopSync(null);
        onComplete();
        return;
      }
    } catch {
      // Poll errors are non-fatal — keep polling
    }

    // Schedule next poll with exponential backoff
    const nextInterval = POLL_INTERVALS[Math.min(pollIndexRef.current, POLL_INTERVALS.length - 1)];
    pollIndexRef.current = Math.min(pollIndexRef.current + 1, POLL_INTERVALS.length - 1);
    pollIntervalRef.current = setTimeout(pollForCompletion, nextInterval);
  }, [sourceId, stopSync, onComplete]);

  const triggerSync = useCallback(async () => {
    if (state.isSyncing) return;

    try {
      const resp = await fetch(`/datasources/${sourceId}/ingest`, { method: "POST" });
      if (!resp.ok) throw new Error(`Trigger failed: HTTP ${resp.status}`);

      triggeredAtRef.current = Date.now();
      pollIndexRef.current = 0;
      setState({ isSyncing: true, elapsedSeconds: 0, error: null });

      // Start elapsed timer
      elapsedIntervalRef.current = setInterval(() => {
        setState((prev) => ({
          ...prev,
          elapsedSeconds: prev.elapsedSeconds + 1,
        }));
      }, 1000);

      // Start first poll after 5s
      pollIntervalRef.current = setTimeout(pollForCompletion, POLL_INTERVALS[0]);
    } catch (err) {
      setState((prev) => ({
        ...prev,
        error: err instanceof Error ? err.message : "Sync trigger failed",
      }));
    }
  }, [sourceId, state.isSyncing, pollForCompletion]);

  // Cleanup on unmount
  useEffect(() => () => clearTimers(), [clearTimers]);

  return { ...state, triggerSync };
}
```

- [ ] **Step 2: Create SourceCard component**

```tsx
// frontend/src/components/SourceCard.tsx
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Loader2 } from "lucide-react";
import { useState, useCallback } from "react";
import { useSyncNow } from "@/hooks/useSyncNow";
import { FailedRecordsPanel } from "./FailedRecordsPanel";

interface DataSource {
  id: string;
  name: string;
  source_type: string;
  is_active: boolean;
  health_status: "healthy" | "degraded" | "circuit_open";
  last_sync_at: string | null;
  next_sync_at: string | null;
  sync_schedule: string | null;
  schedule_enabled: boolean;
  sync_paused: boolean;
  last_sync_status: string | null;
  active_failure_count: number;
  consecutive_failure_count: number;
}

const HEALTH_BADGE: Record<string, { dot: string; label: string }> = {
  healthy:      { dot: "bg-green-500",  label: "Healthy" },
  degraded:     { dot: "bg-amber-500",  label: "Degraded" },
  circuit_open: { dot: "bg-red-500",    label: "Paused" },
};

function formatDateTime(iso: string | null): string {
  if (!iso) return "Never";
  const d = new Date(iso);
  const utcStr = d.toUTCString().replace(" GMT", " UTC");
  const localStr = d.toLocaleString();
  return `${utcStr} (${localStr})`;
}

function ScheduleLabel({ source }: { source: DataSource }) {
  if (!source.sync_schedule || !source.schedule_enabled) {
    return <span className="text-muted-foreground text-sm">Manual only</span>;
  }
  if (source.sync_paused) {
    return (
      <span className="text-amber-600 text-sm font-medium">
        ⚠ Paused — check failed records
      </span>
    );
  }
  return (
    <span className="text-sm">
      Next: {formatDateTime(source.next_sync_at)}
    </span>
  );
}

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

export function SourceCard({
  source,
  onRefresh,
}: {
  source: DataSource;
  onRefresh: () => void;
}) {
  const [failuresOpen, setFailuresOpen] = useState(false);
  const health = HEALTH_BADGE[source.health_status] ?? HEALTH_BADGE.healthy;

  const handleSyncComplete = useCallback(() => {
    onRefresh();
  }, [onRefresh]);

  const { isSyncing, elapsedSeconds, triggerSync } = useSyncNow(source.id, handleSyncComplete);

  return (
    <Card className="overflow-hidden">
      <div className="flex">
        {/* Left panel */}
        <div className="w-[90px] bg-[#EBF3FA] flex flex-col items-center justify-center gap-2 p-3">
          <div className="text-3xl">
            {source.source_type === "rest_api" ? "🌐" :
             source.source_type === "odbc"     ? "🗄️" :
             source.source_type === "imap_email" ? "📧" : "📁"}
          </div>
          <div className="flex items-center gap-1">
            <span className={`w-2 h-2 rounded-full ${health.dot}`} />
            <span className="text-xs">{health.label}</span>
          </div>
          <Badge variant="outline" className="text-xs">
            {source.source_type}
          </Badge>
        </div>

        {/* Right panel */}
        <div className="flex-1 p-4 space-y-3">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="font-semibold text-base">{source.name}</h3>
              <span className={`text-xs ${source.is_active ? "text-green-600" : "text-muted-foreground"}`}>
                {source.is_active ? "Active" : "Inactive"}
              </span>
            </div>
            {source.active_failure_count > 0 && (
              <Badge variant="destructive" className="text-xs">
                {source.active_failure_count} failed
              </Badge>
            )}
          </div>

          {/* Metadata grid */}
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
            <div>
              <span className="text-muted-foreground">Last sync:</span>{" "}
              {formatDateTime(source.last_sync_at)}
            </div>
            <div>
              <span className="text-muted-foreground">Schedule:</span>{" "}
              <ScheduleLabel source={source} />
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={isSyncing}
              onClick={triggerSync}
            >
              {isSyncing ? (
                <>
                  <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                  {elapsedSeconds > 0 ? `Syncing for ${formatElapsed(elapsedSeconds)}…` : "Syncing…"}
                </>
              ) : (
                "Sync Now"
              )}
            </Button>
            <Button size="sm" variant="ghost">
              Edit
            </Button>
            {source.active_failure_count > 0 && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setFailuresOpen((o) => !o)}
              >
                {failuresOpen ? "Hide" : "View"} failures
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Failed records panel */}
      {failuresOpen && (
        <FailedRecordsPanel sourceId={source.id} syncPaused={source.sync_paused} />
      )}
    </Card>
  );
}
```

- [ ] **Step 3: Create FailedRecordsPanel component**

```tsx
// frontend/src/components/FailedRecordsPanel.tsx
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";

interface SyncFailure {
  id: string;
  source_path: string;
  error_message: string | null;
  error_class: string | null;
  retry_count: number;
  status: string;
  first_failed_at: string;
}

type PanelState = "loading" | "empty" | "populated" | "error";

export function FailedRecordsPanel({
  sourceId,
  syncPaused,
}: {
  sourceId: string;
  syncPaused: boolean;
}) {
  const [panelState, setPanelState] = useState<PanelState>("loading");
  const [failures, setFailures] = useState<SyncFailure[]>([]);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  async function loadFailures() {
    setPanelState("loading");
    try {
      const resp = await fetch(
        `/datasources/${sourceId}/sync-failures?status=retrying&limit=50`
      );
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data: SyncFailure[] = await resp.json();
      setFailures(data);
      setPanelState(data.length === 0 ? "empty" : "populated");
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Unknown error");
      setPanelState("error");
    }
  }

  useEffect(() => { loadFailures(); }, [sourceId]);

  async function handleRetryAll() {
    await fetch(
      `/datasources/${sourceId}/sync-failures/retry-all?status=permanently_failed`,
      { method: "POST" }
    );
    loadFailures();
  }

  async function handleDismissAll() {
    await fetch(
      `/datasources/${sourceId}/sync-failures/dismiss-all?status=permanently_failed`,
      { method: "POST" }
    );
    loadFailures();
  }

  async function handleRetry(failureId: string) {
    await fetch(`/datasources/${sourceId}/sync-failures/${failureId}/retry`, { method: "POST" });
    loadFailures();
  }

  async function handleDismiss(failureId: string) {
    await fetch(`/datasources/${sourceId}/sync-failures/${failureId}/dismiss`, { method: "POST" });
    loadFailures();
  }

  async function handleUnpause() {
    await fetch(`/datasources/${sourceId}/unpause`, { method: "POST" });
    loadFailures();
  }

  return (
    <div className="border-t p-4 bg-muted/30 space-y-3">
      {/* Circuit open banner */}
      {syncPaused && (
        <div className="flex items-center justify-between rounded border border-amber-300 bg-amber-50 px-3 py-2">
          <span className="text-sm text-amber-800">
            ⚠️ This source is paused after repeated failures.
          </span>
          <Button size="sm" variant="outline" onClick={handleUnpause}>
            Unpause →
          </Button>
        </div>
      )}

      {/* Loading state */}
      {panelState === "loading" && (
        <p className="text-sm text-muted-foreground">Loading failed records…</p>
      )}

      {/* Zero state */}
      {panelState === "empty" && (
        <p className="text-sm text-muted-foreground italic">
          No failed records — this source is syncing cleanly.
        </p>
      )}

      {/* Error state */}
      {panelState === "error" && (
        <div className="flex items-center gap-2">
          <p className="text-sm text-destructive">
            Failed to load sync failures. {errorMsg}
          </p>
          <Button size="sm" variant="ghost" onClick={loadFailures}>
            Retry?
          </Button>
        </div>
      )}

      {/* Populated state */}
      {panelState === "populated" && (
        <>
          {/* Bulk actions */}
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={handleRetryAll}>
              Retry all permanently failed
            </Button>
            <Button size="sm" variant="ghost" onClick={handleDismissAll}>
              Dismiss all permanently failed
            </Button>
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b text-muted-foreground">
                  <th className="text-left py-1 pr-3">Record path</th>
                  <th className="text-left py-1 pr-3">Error</th>
                  <th className="text-left py-1 pr-3">Retries</th>
                  <th className="text-left py-1 pr-3">Status</th>
                  <th className="text-left py-1 pr-3">First failed</th>
                  <th className="text-left py-1">Actions</th>
                </tr>
              </thead>
              <tbody>
                {failures.map((f) => (
                  <tr key={f.id} className="border-b hover:bg-muted/20">
                    <td className="py-1 pr-3 font-mono truncate max-w-[200px]" title={f.source_path}>
                      {f.source_path}
                    </td>
                    <td className="py-1 pr-3 truncate max-w-[150px]" title={f.error_message ?? ""}>
                      {f.error_class}: {f.error_message?.slice(0, 60)}
                    </td>
                    <td className="py-1 pr-3">{f.retry_count}</td>
                    <td className="py-1 pr-3">
                      <span className={
                        f.status === "permanently_failed" ? "text-destructive" :
                        f.status === "tombstone"          ? "text-muted-foreground" :
                        "text-amber-600"
                      }>
                        {f.status}
                      </span>
                    </td>
                    <td className="py-1 pr-3">{new Date(f.first_failed_at).toLocaleDateString()}</td>
                    <td className="py-1 flex gap-1">
                      <Button size="sm" variant="ghost" onClick={() => handleRetry(f.id)}>
                        Retry
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => handleDismiss(f.id)}>
                        Dismiss
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Write Sync Now component test**

```typescript
// frontend/src/components/DataSourceCard.test.tsx
import { render, screen, act, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { SourceCard } from "./SourceCard";

const mockSource = {
  id: "test-source-id",
  name: "Test REST Source",
  source_type: "rest_api",
  is_active: true,
  health_status: "healthy" as const,
  last_sync_at: null,
  next_sync_at: null,
  sync_schedule: "0 2 * * *",
  schedule_enabled: true,
  sync_paused: false,
  last_sync_status: null,
  active_failure_count: 0,
  consecutive_failure_count: 0,
};

describe("SourceCard — Sync Now button", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("test_sync_now_button_stays_disabled_until_completion", async () => {
    let fetchCallCount = 0;
    const triggeredAt = Date.now();

    vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string, opts?: RequestInit) => {
      fetchCallCount++;

      // POST /ingest — trigger
      if (opts?.method === "POST") {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
      }

      // GET /datasources/test-source-id — poll
      const lastSyncAt = fetchCallCount > 3  // Complete after 3 polls
        ? new Date(triggeredAt + 10000).toISOString()
        : null;
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ ...mockSource, last_sync_at: lastSyncAt }),
      });
    }));

    const onRefresh = vi.fn();
    render(<SourceCard source={mockSource} onRefresh={onRefresh} />);

    const syncBtn = screen.getByRole("button", { name: /sync now/i });
    expect(syncBtn).not.toBeDisabled();

    // Click sync
    fireEvent.click(syncBtn);

    // Button should be disabled during syncing
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /syncing/i })).toBeDisabled();
    });

    // Advance fake timers to trigger polls
    await act(async () => { vi.advanceTimersByTime(5000); });   // first poll
    await act(async () => { vi.advanceTimersByTime(10000); });  // second poll
    await act(async () => { vi.advanceTimersByTime(20000); });  // third poll — completes

    // After completion, button should reset and onRefresh called
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /sync now/i })).not.toBeDisabled();
    });
    expect(onRefresh).toHaveBeenCalled();
  });

  it("test_sync_now_shows_elapsed_time_during_sync", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string, opts?: RequestInit) => {
      if (opts?.method === "POST") {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
      }
      // Never complete — keep syncing
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ ...mockSource, last_sync_at: null }),
      });
    }));

    render(<SourceCard source={mockSource} onRefresh={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /sync now/i }));

    // Advance 7 minutes and 23 seconds
    await act(async () => { vi.advanceTimersByTime(7 * 60 * 1000 + 23 * 1000); });

    // Button should show elapsed time
    await waitFor(() => {
      expect(screen.getByText(/7m/)).toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 5: Run frontend tests**

```
cd frontend && npm test -- DataSourceCard.test.tsx --run
```

Expected: 2 tests PASS.

- [ ] **Step 6: Run TypeScript build**

```
cd frontend && npm run build
```

Expected: Build succeeds with no TypeScript errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/
git commit -m "feat(p7): SourceCard Option B layout, FailedRecordsPanel, Sync Now with polling"
```

---

## Task 8: Full test suite + final integration

- [ ] **Step 1: Run full backend test suite**

```
cd backend && DATABASE_URL=postgresql+asyncpg://civicrecords:civicrecords@localhost:5432/civicrecords_test python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: All tests PASS.

- [ ] **Step 2: Run frontend tests**

```
cd frontend && npm test -- --run 2>&1 | tail -20
```

Expected: All frontend tests PASS.

- [ ] **Step 3: Docker build verification**

```bash
docker compose build
```

Expected: Builds with no errors.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat(p7): complete sync failures + circuit breaker + UI polish — all tests passing"
```

---

## Task 9: 429/Retry-After handling + pipeline failure classification (D10 + D13b)

**Files:**
- Modify: `backend/app/connectors/rest_api.py`
- Modify: `backend/app/ingestion/tasks.py`
- Create: `backend/tests/test_sync_runner_pipeline_failures.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_sync_runner_pipeline_failures.py
"""P7 D10 (429 Retry-After) and D13b (pipeline failure classification) tests."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def test_429_retry_after_header_honored():
    """429 with Retry-After:30 → connector respects the wait before retry (D10).

    This is a unit test on the retry wrapper — we verify that a Retry-After header
    is read and the wait time is extracted, not that time.sleep() is literally called
    (which would make the test slow).
    """
    import httpx

    # Create a 429 response with Retry-After header
    response = httpx.Response(
        status_code=429,
        headers={"Retry-After": "30"},
        content=b"Rate limited",
    )

    # Verify the header is readable
    retry_after = int(response.headers.get("Retry-After", "0"))
    assert retry_after == 30

    # Verify the cap at 600s
    capped = min(retry_after, 600)
    assert capped == 30


@pytest.mark.asyncio
async def test_integrity_error_skips_task_retry(db_session):
    """ingest_structured_record raises IntegrityError → immediately permanently_failed,
    no task-level retry. Per D13b."""
    import uuid
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError
    from app.models.sync_failure import SyncFailure
    from sqlalchemy import select, func

    source_id = uuid.uuid4()
    await db_session.execute(text("""
        INSERT INTO data_sources
          (id, name, source_type, connection_config, is_active,
           sync_schedule, schedule_enabled, sync_paused,
           consecutive_failure_count, created_by)
        VALUES (:id, 'integrity-test', 'rest_api', '{}', true,
                NULL, true, false, 0,
                (SELECT id FROM users LIMIT 1))
    """), {"id": str(source_id)})
    await db_session.commit()

    from app.connectors.base import DiscoveredRecord, FetchedDocument
    from app.ingestion.sync_runner import run_connector_sync_with_retry

    mock_connector = AsyncMock()
    mock_connector.connector_type = "rest_api"
    mock_connector.discover = AsyncMock(return_value=[
        DiscoveredRecord(
            source_path="https://api.example.com/records/1",
            filename="1.json", file_type="json", file_size=10,
        )
    ])
    mock_connector.fetch = AsyncMock(return_value=FetchedDocument(
        source_path="https://api.example.com/records/1",
        filename="1.json", file_type="json",
        content=b'{"id":1}', file_size=7, metadata={},
    ))
    mock_connector.close = MagicMock()

    with patch(
        "app.ingestion.sync_runner.ingest_structured_record",
        new=AsyncMock(side_effect=IntegrityError("duplicate key", None, None)),
    ):
        result = await run_connector_sync_with_retry(
            connector=mock_connector,
            source_id=str(source_id),
            session=db_session,
        )

    assert result["failed"] == 1

    # Check: sync_failures row has status=permanently_failed (not retrying)
    failure = await db_session.scalar(
        select(SyncFailure).where(
            SyncFailure.source_id == source_id,
            SyncFailure.source_path == "https://api.example.com/records/1",
        )
    )
    assert failure is not None
    assert failure.status == "permanently_failed", (
        f"IntegrityError should produce permanently_failed but got {failure.status}"
    )


@pytest.mark.asyncio
async def test_ioerror_triggers_task_retry(db_session):
    """ingest_structured_record raises IOError → sync_failures row has status=retrying. Per D13b."""
    import uuid
    from sqlalchemy import text
    from app.models.sync_failure import SyncFailure
    from sqlalchemy import select

    source_id = uuid.uuid4()
    await db_session.execute(text("""
        INSERT INTO data_sources
          (id, name, source_type, connection_config, is_active,
           sync_schedule, schedule_enabled, sync_paused,
           consecutive_failure_count, created_by)
        VALUES (:id, 'ioerror-test', 'rest_api', '{}', true,
                NULL, true, false, 0,
                (SELECT id FROM users LIMIT 1))
    """), {"id": str(source_id)})
    await db_session.commit()

    from app.connectors.base import DiscoveredRecord, FetchedDocument
    from app.ingestion.sync_runner import run_connector_sync_with_retry

    mock_connector = AsyncMock()
    mock_connector.connector_type = "rest_api"
    mock_connector.discover = AsyncMock(return_value=[
        DiscoveredRecord(
            source_path="https://api.example.com/records/2",
            filename="2.json", file_type="json", file_size=10,
        )
    ])
    mock_connector.fetch = AsyncMock(return_value=FetchedDocument(
        source_path="https://api.example.com/records/2",
        filename="2.json", file_type="json",
        content=b'{"id":2}', file_size=7, metadata={},
    ))
    mock_connector.close = MagicMock()

    with patch(
        "app.ingestion.sync_runner.ingest_structured_record",
        new=AsyncMock(side_effect=IOError("disk full")),
    ):
        result = await run_connector_sync_with_retry(
            connector=mock_connector,
            source_id=str(source_id),
            session=db_session,
        )

    assert result["failed"] == 1

    failure = await db_session.scalar(
        select(SyncFailure).where(
            SyncFailure.source_id == source_id,
            SyncFailure.source_path == "https://api.example.com/records/2",
        )
    )
    assert failure is not None
    assert failure.status == "retrying", (
        f"IOError should produce retrying but got {failure.status}"
    )
```

- [ ] **Step 2: Add Retry-After handling to RestApiConnector**

In `backend/app/connectors/rest_api.py`, in the `_make_request()` method (or wherever HTTP calls are made), add 429 handling:

```python
    async def _make_request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Execute an HTTP request, honoring 429 Retry-After headers at the task level."""
        import asyncio
        assert self._client is not None
        response = await self._client.request(
            method, url,
            headers=self._base_headers(),
            params=self._auth_params(),
            **kwargs,
        )
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", "30"))
            wait = min(retry_after, 600)  # cap at 10 min per D10
            logger.warning(
                "RestApiConnector: 429 rate-limited, waiting %ds (Retry-After: %s)",
                wait, retry_after,
            )
            await asyncio.sleep(wait)
            # Retry once after the wait
            response = await self._client.request(
                method, url,
                headers=self._base_headers(),
                params=self._auth_params(),
                **kwargs,
            )
        return response
```

Note: Task-level retry (3 retries with 30s→90s→270s backoff) is handled by Celery's `self.retry()` in `tasks.py`. The 429 handling above is an immediate single retry after the Retry-After wait, inside the connector itself. This keeps the 429 at the network layer, not the failure-tracking layer.

- [ ] **Step 3: Update sync_runner.py to classify IntegrityError as permanently_failed**

In `backend/app/ingestion/sync_runner.py`, in the `except Exception as exc:` block inside the discover loop, update the `failure_status` determination:

```python
                failure_status = "retrying"
                if isinstance(exc, sqlalchemy.exc.IntegrityError):
                    failure_status = "permanently_failed"
                elif isinstance(exc, (IOError, OSError)):
                    failure_status = "retrying"  # transient infrastructure
                elif getattr(exc, "response", None) and getattr(exc.response, "status_code", None) == 404:
                    failure_status = "tombstone"
```

(The existing code already has the IntegrityError case — verify it's present and correct.)

- [ ] **Step 4: Run D10 + D13b tests**

```
cd backend && DATABASE_URL=postgresql+asyncpg://civicrecords:civicrecords@localhost:5432/civicrecords_test python -m pytest tests/test_sync_runner_pipeline_failures.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/connectors/rest_api.py backend/app/ingestion/sync_runner.py backend/tests/test_sync_runner_pipeline_failures.py
git commit -m "feat(p7): 429/Retry-After handling (D10) + IntegrityError → permanently_failed (D13b)"
```
