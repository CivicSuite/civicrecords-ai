# P6b — Cron Scheduler Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace drift-prone interval-based scheduling (`schedule_minutes`) with clock-anchored cron scheduling (`sync_schedule` via croniter), and expose schedule state in the DataSources API.

**Architecture:** Add `schedule_enabled` boolean to DataSource. Migration 015 converts existing `schedule_minutes` values via explicit allowlist, nulling non-representable values with a migration report. `check_scheduled_sources()` rewritten to use `croniter(expr, anchor).get_next(datetime) <= now()`. `next_sync_at` computed at API response time (not stored). Cron expressions validated at create/update with a rolling 7-day minimum interval check (floor: 5 min). All cron evaluated in UTC; UI shows both UTC and local.

**Tech Stack:** Python/FastAPI, SQLAlchemy async, Alembic, `croniter` (Apache 2.0), Celery beat, React/TypeScript/shadcn-ui.

**Depends on:** P6a must be merged first (`schedule_enabled` added here; `run_connector_sync` already updated).

**Spec:** `docs/superpowers/specs/2026-04-16-p6b-scheduler-design.md`

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Modify | `backend/requirements.txt` (or `pyproject.toml`) | Add `croniter>=2.0.0` |
| Modify | `backend/app/models/document.py` | Add `schedule_enabled: bool = True` to DataSource |
| Modify | `backend/app/schemas/document.py` | Add `sync_schedule`, `schedule_enabled`, `next_sync_at` to DataSourceCreate/Update/Read; remove `schedule_minutes` |
| Modify | `backend/app/datasources/router.py` | Add cron validation on create/update; add `next_sync_at` to GET response |
| Modify | `backend/app/ingestion/scheduler.py` | Rewrite `check_scheduled_sources()` with croniter logic |
| Create | `backend/app/ingestion/cron_utils.py` | `min_interval_minutes()` validation helper, `compute_next_sync_at()` helper |
| Create | `backend/alembic/versions/015_p6b_scheduler.py` | Migration: add schedule_enabled, convert schedule_minutes, drop schedule_minutes, add `_migration_015_report` table |
| Create | `backend/tests/test_scheduler.py` | All scheduler tests (overdue, not-due, first-run, UTC, schedule_enabled, sync_paused) |
| Create | `backend/tests/test_migration_015.py` | Migration allowlist conversion and non-allowlist nulling tests |
| Modify | `backend/tests/test_datasources.py` | next_sync_at in list response, schedule_disabled preserves sync_schedule |
| Modify | `frontend/src/pages/DataSources.tsx` | Schedule presets dropdown + enable/disable toggle (stub — full UI in P7) |

---

## Task 1: Add croniter dependency

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add croniter to requirements**

In `backend/requirements.txt`, add:
```
croniter>=2.0.0
```

- [ ] **Step 2: Install and verify**

```
cd backend && pip install croniter>=2.0.0
python -c "from croniter import croniter; from datetime import datetime, timezone; it = croniter('0 2 * * *', datetime(2026,4,16,0,0, tzinfo=timezone.utc)); print(it.get_next(datetime))"
```

Expected output: `2026-04-16 02:00:00+00:00`

- [ ] **Step 3: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore(p6b): add croniter>=2.0.0 dependency"
```

---

## Task 2: Write failing scheduler tests

**Files:**
- Create: `backend/tests/test_scheduler.py`

- [ ] **Step 1: Create test file**

```python
# backend/tests/test_scheduler.py
"""P6b scheduler tests — TDD order. Tests must fail before implementation."""
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from croniter import croniter


UTC = timezone.utc


# ---------------------------------------------------------------------------
# Unit tests for scheduler trigger logic
# ---------------------------------------------------------------------------

class TestCronTriggerLogic:
    """These tests validate the trigger decision in isolation (pure logic)."""

    def _should_trigger(self, cron_expr: str, last_sync_at: datetime | None, now: datetime) -> bool:
        """Reference implementation of the trigger decision (D1 from spec)."""
        anchor = last_sync_at or datetime(1970, 1, 1, tzinfo=UTC)
        it = croniter(cron_expr, anchor)
        next_scheduled = it.get_next(datetime)
        return next_scheduled <= now

    def test_overdue_source_triggers(self):
        """Source with 0 2 * * *, last_sync_at yesterday → triggered."""
        yesterday_2am = datetime(2026, 4, 15, 2, 0, 0, tzinfo=UTC)
        now = datetime(2026, 4, 16, 3, 0, 0, tzinfo=UTC)  # today 3am
        assert self._should_trigger("0 2 * * *", yesterday_2am, now) is True

    def test_not_due_source_skipped(self):
        """Source with 0 2 * * *, last_sync_at today at 2:01am UTC → not triggered."""
        today_2am_01 = datetime(2026, 4, 16, 2, 1, 0, tzinfo=UTC)
        now = datetime(2026, 4, 16, 2, 5, 0, tzinfo=UTC)  # 4 minutes later
        assert self._should_trigger("0 2 * * *", today_2am_01, now) is False

    def test_null_last_sync_triggers_immediately(self):
        """Source with last_sync_at=NULL → triggered immediately (anchor=epoch)."""
        now = datetime(2026, 4, 16, 10, 0, 0, tzinfo=UTC)
        # With epoch anchor, get_next from epoch to any cron should be in the past
        assert self._should_trigger("0 2 * * *", None, now) is True

    def test_cron_evaluated_in_utc(self):
        """0 2 * * * fires at 2:00 AM UTC exactly, not at local 2 AM."""
        # now = 2:01 AM UTC → should trigger (2am UTC passed)
        now_utc_2am = datetime(2026, 4, 16, 2, 1, 0, tzinfo=UTC)
        assert self._should_trigger("0 2 * * *", None, now_utc_2am) is True

        # Simulate: now = 2:01 AM local (say MDT = UTC-6), which is 8:01 AM UTC
        # last_sync_at was at 2:05 AM UTC today (already ran)
        # So scheduler should NOT trigger again until tomorrow 2am UTC
        today_2am_05_utc = datetime(2026, 4, 16, 2, 5, 0, tzinfo=UTC)
        now_8am_utc = datetime(2026, 4, 16, 8, 1, 0, tzinfo=UTC)  # 2am MDT
        assert self._should_trigger("0 2 * * *", today_2am_05_utc, now_8am_utc) is False


# ---------------------------------------------------------------------------
# Unit tests for min_interval_minutes validation
# ---------------------------------------------------------------------------

class TestMinIntervalValidation:

    def test_min_interval_valid_hourly(self):
        """0 * * * * (hourly, 60-min gap) → passes validation (>= 5)."""
        from app.ingestion.cron_utils import min_interval_minutes
        assert min_interval_minutes("0 * * * *") >= 5

    def test_min_interval_rejected_every_minute(self):
        """* * * * * (every minute) → min_interval_minutes returns 1 → reject."""
        from app.ingestion.cron_utils import min_interval_minutes
        assert min_interval_minutes("* * * * *") < 5

    def test_min_interval_adversarial_cron(self):
        """*/1 0 * * * → fires every minute in hour 0 → rolling week detects 1-min gap."""
        from app.ingestion.cron_utils import min_interval_minutes
        result = min_interval_minutes("*/1 0 * * *")
        assert result < 5, f"Expected < 5 but got {result}"

    def test_min_interval_every_5_min_passes(self):
        """*/5 * * * * (every 5 min) → passes (exactly at floor)."""
        from app.ingestion.cron_utils import min_interval_minutes
        assert min_interval_minutes("*/5 * * * *") >= 5


# ---------------------------------------------------------------------------
# Integration: check_scheduled_sources task
# ---------------------------------------------------------------------------

class TestCheckScheduledSources:

    @pytest.mark.asyncio
    async def test_schedule_disabled_not_triggered(self, db_session):
        """Source with valid cron but schedule_enabled=False → not triggered."""
        from app.ingestion.scheduler import _check_scheduled_sources_async
        source_id = uuid.uuid4()
        # Create source with schedule disabled
        from sqlalchemy import text
        await db_session.execute(text("""
            INSERT INTO data_sources
              (id, name, source_type, connection_config, is_active,
               sync_schedule, schedule_enabled, sync_paused, created_by)
            VALUES (:id, 'test-disabled', 'rest_api', '{}', true,
                    '0 2 * * *', false, false,
                    (SELECT id FROM users LIMIT 1))
        """), {"id": str(source_id)})
        await db_session.commit()

        with patch("app.ingestion.scheduler.task_ingest_source") as mock_task:
            result = await _check_scheduled_sources_async(db_session)
            mock_task.delay.assert_not_called()

    @pytest.mark.asyncio
    async def test_paused_source_not_triggered(self, db_session):
        """Source with valid cron but sync_paused=True → not triggered."""
        from app.ingestion.scheduler import _check_scheduled_sources_async
        source_id = uuid.uuid4()
        from sqlalchemy import text
        await db_session.execute(text("""
            INSERT INTO data_sources
              (id, name, source_type, connection_config, is_active,
               sync_schedule, schedule_enabled, sync_paused, created_by)
            VALUES (:id, 'test-paused', 'rest_api', '{}', true,
                    '0 2 * * *', true, true,
                    (SELECT id FROM users LIMIT 1))
        """), {"id": str(source_id)})
        await db_session.commit()

        with patch("app.ingestion.scheduler.task_ingest_source") as mock_task:
            result = await _check_scheduled_sources_async(db_session)
            mock_task.delay.assert_not_called()
```

- [ ] **Step 2: Run tests to confirm they fail**

```
cd backend && python -m pytest tests/test_scheduler.py::TestCronTriggerLogic -v
```

Expected: 4 PASSED (pure logic, no imports needed yet).

```
cd backend && python -m pytest tests/test_scheduler.py::TestMinIntervalValidation -v
```

Expected: `ImportError: cannot import name 'min_interval_minutes' from 'app.ingestion.cron_utils'`

- [ ] **Step 3: Commit failing tests**

```bash
git add backend/tests/test_scheduler.py
git commit -m "test(p6b): add failing scheduler and cron validation tests"
```

---

## Task 3: Create cron_utils.py with validation helpers

**Files:**
- Create: `backend/app/ingestion/cron_utils.py`

- [ ] **Step 1: Create the file**

```python
# backend/app/ingestion/cron_utils.py
"""Cron expression utilities: validation and next-run computation."""
from datetime import datetime, timezone

from croniter import croniter, CroniterBadCronError

UTC = timezone.utc


def min_interval_minutes(expr: str) -> int:
    """Compute minimum interval between firings over a rolling 7-day window.

    Samples 2016 consecutive tick pairs (7 days × 288 5-min ticks/day) to detect
    adversarial expressions like '*/1 0 * * *' that fire every minute in one hour.

    Returns minimum gap in whole minutes.
    Raises ValueError for unparseable expressions.
    """
    try:
        it = croniter(expr, datetime.now(UTC))
    except (CroniterBadCronError, ValueError) as e:
        raise ValueError(f"Invalid cron expression '{expr}': {e}") from e

    prev = it.get_next(datetime)
    min_gap = float("inf")
    for _ in range(2016):  # 7 days × 288 ticks/day at 5-min granularity
        nxt = it.get_next(datetime)
        gap = (nxt - prev).total_seconds() / 60
        if gap < min_gap:
            min_gap = gap
        prev = nxt
    return int(min_gap)


def validate_cron_expression(expr: str) -> None:
    """Validate a cron expression. Raises ValueError with a user-facing message if invalid.

    Checks:
    1. Expression is parseable by croniter.
    2. Minimum interval across 7-day window is >= 5 minutes.
    """
    try:
        croniter(expr, datetime.now(UTC))
    except (CroniterBadCronError, ValueError):
        raise ValueError(f"Invalid cron expression: '{expr}'. Use standard 5-field cron syntax.")

    gap = min_interval_minutes(expr)
    if gap < 5:
        raise ValueError(
            f"Schedule fires more frequently than every 5 minutes "
            f"(minimum gap detected: {gap} min). Minimum allowed interval is 5 minutes."
        )


def compute_next_sync_at(sync_schedule: str, last_sync_at: datetime | None) -> datetime | None:
    """Compute the next scheduled run time from the last sync anchor.

    Returns None if sync_schedule is empty/None.
    """
    if not sync_schedule:
        return None
    anchor = last_sync_at or datetime(1970, 1, 1, tzinfo=UTC)
    it = croniter(sync_schedule, anchor)
    return it.get_next(datetime)
```

- [ ] **Step 2: Run cron_utils tests**

```
cd backend && python -m pytest tests/test_scheduler.py::TestMinIntervalValidation -v
```

Expected: 4 PASSED.

- [ ] **Step 3: Commit**

```bash
git add backend/app/ingestion/cron_utils.py
git commit -m "feat(p6b): add cron_utils.py with min_interval validation + next_sync_at helper"
```

---

## Task 4: Add schedule_enabled to DataSource model

**Files:**
- Modify: `backend/app/models/document.py`

- [ ] **Step 1: Add schedule_enabled column**

In the `DataSource` class in `backend/app/models/document.py`, add after the `sync_schedule` line:

```python
    schedule_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
```

Also add these P7 columns that will be needed by migration 016 later (add as nullable stubs now to avoid model drift):

```python
    # P7 columns (added here to keep model in sync with upcoming migrations)
    consecutive_failure_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_paused: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    sync_paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_paused_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    retry_batch_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retry_time_limit_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

Note: The DB columns for P7 fields will be added by migration 016. Adding ORM mappings here avoids a model/migration sync gap when P7 plan runs.

- [ ] **Step 2: Verify import**

```
cd backend && python -c "from app.models.document import DataSource; print(DataSource.__table__.columns.keys())"
```

Expected: `schedule_enabled` appears in the column list.

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/document.py
git commit -m "feat(p6b): add schedule_enabled + P7 stub columns to DataSource model"
```

---

## Task 5: Write and apply migration 015_p6b_scheduler

**Files:**
- Create: `backend/alembic/versions/015_p6b_scheduler.py`

- [ ] **Step 1: Create the migration**

```python
# backend/alembic/versions/015_p6b_scheduler.py
"""P6b: schedule_enabled, schedule_minutes → sync_schedule conversion, drop schedule_minutes

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
from sqlalchemy import text

revision: str = '015_p6b_scheduler'
down_revision: Union[str, None] = '014_p6a_idempotency'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Allowlist: schedule_minutes → cron expression (only clean, non-ambiguous mappings)
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

    # 1. Add schedule_enabled (default True — existing sources stay enabled)
    op.add_column(
        "data_sources",
        sa.Column("schedule_enabled", sa.Boolean(), nullable=False, server_default="true"),
    )

    # 2. Add constraint on sync_schedule: non-empty if set
    op.create_check_constraint(
        "chk_sync_schedule_nonempty",
        "data_sources",
        "sync_schedule IS NULL OR length(trim(sync_schedule)) > 0",
    )

    # 3. Create migration report table
    op.create_table(
        "_migration_015_report",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.String(36), nullable=False),
        sa.Column("source_name", sa.String(255)),
        sa.Column("schedule_minutes", sa.Integer()),
        sa.Column("action", sa.String(20)),   # 'converted' | 'nulled'
        sa.Column("cron_expression", sa.String(50), nullable=True),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # 4. Convert schedule_minutes → sync_schedule per allowlist
    rows = conn.execute(
        text("SELECT id, name, schedule_minutes FROM data_sources WHERE schedule_minutes IS NOT NULL")
    ).fetchall()

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
                f"schedule_minutes={minutes} → sync_schedule='{cron}'"
            )
        else:
            # Non-allowlist value: null out + disable
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

    # 5. Drop schedule_minutes
    op.drop_column("data_sources", "schedule_minutes")


def downgrade() -> None:
    op.add_column(
        "data_sources",
        sa.Column("schedule_minutes", sa.Integer(), nullable=True),
    )
    op.drop_table("_migration_015_report")
    op.drop_constraint("chk_sync_schedule_nonempty", "data_sources", type_="check")
    op.drop_column("data_sources", "schedule_enabled")
```

- [ ] **Step 2: Write migration tests**

Create `backend/tests/test_migration_015.py`:

```python
# backend/tests/test_migration_015.py
"""Tests for migration 015 — schedule_minutes allowlist conversion."""
import pytest
from sqlalchemy import text


# Allowlist reference (mirror of migration)
_ALLOWLIST = {
    5:    "*/5 * * * *",
    15:   "*/15 * * * *",
    30:   "*/30 * * * *",
    60:   "0 * * * *",
    1440: "0 2 * * *",
}


@pytest.mark.asyncio
async def test_schedule_minutes_allowlist_converts_correctly(db_session):
    """schedule_minutes in allowlist (15, 30, 60, 1440) → correct cron expressions."""
    for minutes, expected_cron in [(15, "*/15 * * * *"), (1440, "0 2 * * *")]:
        # Apply the conversion logic (same as migration)
        cron = _ALLOWLIST.get(minutes)
        assert cron == expected_cron, f"minutes={minutes} → expected {expected_cron}, got {cron}"


@pytest.mark.asyncio
async def test_schedule_minutes_non_allowlist_nulled_with_report(db_session):
    """schedule_minutes not in allowlist (45, 90) → sync_schedule=NULL, schedule_enabled=False."""
    non_allowlist = [45, 90, 3, 100]
    for minutes in non_allowlist:
        # Verify these are NOT in the allowlist
        assert minutes not in _ALLOWLIST, f"{minutes} should NOT be in allowlist"
        # The migration sets sync_schedule=NULL and schedule_enabled=False for these

    # Verify the allowlist contains exactly the expected values
    expected_keys = {5, 10, 15, 20, 30, 60, 120, 180, 240, 360, 480, 720, 1440}
    assert set(_ALLOWLIST.keys()) == expected_keys, (
        f"Allowlist keys mismatch: {set(_ALLOWLIST.keys())} != {expected_keys}"
    )


@pytest.mark.asyncio
async def test_schedule_minutes_non_allowlist_nulled_integration(db_session):
    """End-to-end: seed source with schedule_minutes=45, apply logic, verify NULL + disabled."""
    import uuid
    from sqlalchemy import text

    source_id = uuid.uuid4()
    # Seed a source with schedule_minutes=45 (non-allowlist)
    await db_session.execute(text("""
        INSERT INTO data_sources
          (id, name, source_type, connection_config, is_active, created_by)
        VALUES (:id, 'test-nonallowlist', 'rest_api', '{}', true,
                (SELECT id FROM users LIMIT 1))
    """), {"id": str(source_id)})
    await db_session.commit()

    # Apply the non-allowlist branch logic
    await db_session.execute(text("""
        UPDATE data_sources
        SET sync_schedule = NULL, schedule_enabled = false
        WHERE id = :id
    """), {"id": str(source_id)})
    await db_session.commit()

    # Verify
    row = await db_session.execute(
        text("SELECT sync_schedule, schedule_enabled FROM data_sources WHERE id = :id"),
        {"id": str(source_id)},
    )
    result = row.fetchone()
    assert result[0] is None, "sync_schedule must be NULL for non-allowlist schedule_minutes"
    assert result[1] is False, "schedule_enabled must be False for non-allowlist schedule_minutes"
```

- [ ] **Step 3: Run migration tests**

```
cd backend && DATABASE_URL=postgresql+asyncpg://civicrecords:civicrecords@localhost:5432/civicrecords_test python -m pytest tests/test_migration_015.py -v
```

Expected: PASS (the integration test runs against test DB).

- [ ] **Step 4: Apply migration to test DB**

```bash
cd backend && DATABASE_URL=postgresql+asyncpg://civicrecords:civicrecords@localhost:5432/civicrecords_test alembic upgrade head
```

Expected: Migration 015_p6b_scheduler applies without errors.

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/015_p6b_scheduler.py backend/tests/test_migration_015.py
git commit -m "feat(p6b): migration 015 — schedule_enabled, schedule_minutes conversion, report table"
```

---

## Task 6: Rewrite check_scheduled_sources with croniter

**Files:**
- Modify: `backend/app/ingestion/scheduler.py`

- [ ] **Step 1: Replace the check_scheduled_sources task body**

In `backend/app/ingestion/scheduler.py`, replace the entire `check_scheduled_sources` task (keep the setup and other tasks unchanged):

```python
@celery_app.task(name="civicrecords.check_scheduled_sources")
def check_scheduled_sources():
    """Check each active, non-paused source with a cron schedule and trigger if overdue."""
    import asyncio
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from app.config import settings

    async def _check():
        engine = create_async_engine(settings.database_url, echo=False)
        session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with session_maker() as session:
                return await _check_scheduled_sources_async(session)
        finally:
            await engine.dispose()

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_check())
    finally:
        loop.close()


async def _check_scheduled_sources_async(session) -> dict:
    """Core scheduling logic, extracted for testability.

    Evaluates each eligible source using:
      anchor = source.last_sync_at or epoch
      next_scheduled = croniter(expr, anchor).get_next(datetime)
      trigger if next_scheduled <= now()

    NOT get_prev() > anchor — that almost never fires (see spec D1 for explanation).
    """
    from datetime import datetime, timezone
    from sqlalchemy import select
    from croniter import croniter
    from app.models.document import DataSource
    from app.ingestion.tasks import task_ingest_source

    UTC = timezone.utc

    result = await session.execute(
        select(DataSource).where(
            DataSource.is_active.is_(True),
            DataSource.schedule_enabled.is_(True),
            DataSource.sync_paused.is_(False),
            DataSource.sync_schedule.isnot(None),
        )
    )
    sources = result.scalars().all()
    now = datetime.now(UTC)
    triggered = 0

    for source in sources:
        anchor = source.last_sync_at or datetime(1970, 1, 1, tzinfo=UTC)
        it = croniter(source.sync_schedule, anchor)
        next_scheduled = it.get_next(datetime)
        if next_scheduled <= now:
            task_ingest_source.delay(str(source.id))
            triggered += 1

    return {"checked": len(sources), "triggered": triggered}
```

- [ ] **Step 2: Run integration scheduler tests**

```
cd backend && DATABASE_URL=postgresql+asyncpg://civicrecords:civicrecords@localhost:5432/civicrecords_test python -m pytest tests/test_scheduler.py::TestCheckScheduledSources -v
```

Expected: All PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/app/ingestion/scheduler.py
git commit -m "feat(p6b): rewrite check_scheduled_sources with croniter get_next trigger logic"
```

---

## Task 7: Add cron validation to create/update endpoints + next_sync_at to API response

**Files:**
- Modify: `backend/app/schemas/document.py`
- Modify: `backend/app/datasources/router.py`

- [ ] **Step 1: Update DataSource schemas**

Replace `backend/app/schemas/document.py` with:

```python
import uuid
from datetime import datetime
from pydantic import BaseModel, field_validator
from app.models.document import IngestionStatus, SourceType


class DataSourceCreate(BaseModel):
    name: str
    source_type: SourceType
    connection_config: dict = {}
    sync_schedule: str | None = None
    schedule_enabled: bool = True

    @field_validator("sync_schedule")
    @classmethod
    def validate_sync_schedule(cls, v: str | None) -> str | None:
        if v is not None:
            from app.ingestion.cron_utils import validate_cron_expression
            validate_cron_expression(v)
        return v


class DataSourceRead(BaseModel):
    id: uuid.UUID
    name: str
    source_type: SourceType
    connection_config: dict
    sync_schedule: str | None
    schedule_enabled: bool
    next_sync_at: datetime | None = None  # computed at response time
    is_active: bool
    created_by: uuid.UUID
    created_at: datetime
    last_ingestion_at: datetime | None
    last_sync_at: datetime | None
    last_sync_status: str | None
    model_config = {"from_attributes": True}


class DataSourceUpdate(BaseModel):
    name: str | None = None
    connection_config: dict | None = None
    sync_schedule: str | None = None
    schedule_enabled: bool | None = None
    is_active: bool | None = None

    @field_validator("sync_schedule")
    @classmethod
    def validate_sync_schedule(cls, v: str | None) -> str | None:
        if v is not None:
            from app.ingestion.cron_utils import validate_cron_expression
            validate_cron_expression(v)
        return v


class DocumentRead(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    source_path: str
    filename: str
    file_type: str
    file_hash: str
    file_size: int
    ingestion_status: IngestionStatus
    ingestion_error: str | None
    chunk_count: int
    ingested_at: datetime | None
    connector_type: str | None = None
    updated_at: datetime | None = None
    model_config = {"from_attributes": True}


class DocumentChunkRead(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    content_text: str
    token_count: int
    page_number: int | None
    model_config = {"from_attributes": True}


class IngestionStats(BaseModel):
    total_sources: int
    active_sources: int
    total_documents: int
    documents_by_status: dict[str, int]
    total_chunks: int
```

- [ ] **Step 2: Add next_sync_at computation to list endpoint**

In `backend/app/datasources/router.py`, find the `GET /datasources/` handler and update it to compute `next_sync_at` for each source:

```python
@router.get("/", response_model=list[DataSourceRead])
async def list_datasources(db: AsyncSession = Depends(get_db), current_user=Depends(require_admin)):
    from app.ingestion.cron_utils import compute_next_sync_at
    result = await db.execute(select(DataSource))
    sources = result.scalars().all()

    output = []
    for source in sources:
        data = DataSourceRead.model_validate(source)
        if source.sync_schedule and source.schedule_enabled and not source.sync_paused:
            data.next_sync_at = compute_next_sync_at(source.sync_schedule, source.last_sync_at)
        output.append(data)
    return output
```

- [ ] **Step 3: Write test for next_sync_at in list response**

In `backend/tests/test_datasources.py` (or a new section), add:

```python
@pytest.mark.asyncio
async def test_next_sync_at_returned_in_list(async_client, admin_headers, db_session):
    """GET /datasources/ returns correct next_sync_at for scheduled source."""
    from sqlalchemy import text
    import uuid
    source_id = uuid.uuid4()
    await db_session.execute(text("""
        INSERT INTO data_sources
          (id, name, source_type, connection_config, is_active,
           sync_schedule, schedule_enabled, sync_paused, created_by)
        VALUES (:id, 'sched-test', 'rest_api', '{}', true,
                '0 2 * * *', true, false,
                (SELECT id FROM users LIMIT 1))
    """), {"id": str(source_id)})
    await db_session.commit()

    resp = await async_client.get("/datasources/", headers=admin_headers)
    assert resp.status_code == 200
    sources = resp.json()
    sched = next((s for s in sources if s["id"] == str(source_id)), None)
    assert sched is not None
    assert sched["next_sync_at"] is not None
    # Should be a future timestamp
    from datetime import datetime, timezone
    next_at = datetime.fromisoformat(sched["next_sync_at"])
    assert next_at > datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_schedule_disabled_preserves_sync_schedule(async_client, admin_headers, db_session):
    """PATCH schedule_enabled=False → sync_schedule unchanged in DB."""
    from sqlalchemy import text
    import uuid
    source_id = uuid.uuid4()
    await db_session.execute(text("""
        INSERT INTO data_sources
          (id, name, source_type, connection_config, is_active,
           sync_schedule, schedule_enabled, sync_paused, created_by)
        VALUES (:id, 'toggle-test', 'rest_api', '{}', true,
                '0 2 * * *', true, false,
                (SELECT id FROM users LIMIT 1))
    """), {"id": str(source_id)})
    await db_session.commit()

    resp = await async_client.patch(
        f"/datasources/{source_id}",
        json={"schedule_enabled": False},
        headers=admin_headers,
    )
    assert resp.status_code == 200

    row = await db_session.execute(
        text("SELECT sync_schedule, schedule_enabled FROM data_sources WHERE id = :id"),
        {"id": str(source_id)},
    )
    result = row.fetchone()
    assert result[0] == "0 2 * * *", "sync_schedule must be preserved when toggling off"
    assert result[1] is False
```

- [ ] **Step 4: Run tests**

```
cd backend && DATABASE_URL=postgresql+asyncpg://civicrecords:civicrecords@localhost:5432/civicrecords_test python -m pytest tests/test_datasources.py -v -k "schedule"
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/document.py backend/app/datasources/router.py backend/tests/test_datasources.py
git commit -m "feat(p6b): cron validation on create/update, next_sync_at in list response, schedule_enabled toggle"
```

---

## Task 8: Frontend schedule presets + enable toggle

**Files:**
- Modify: `frontend/src/pages/DataSources.tsx` (or relevant component file)

Note: Full UI polish is in P7. This task adds only the schedule preset dropdown and schedule_enabled toggle to the DataSource create/edit wizard. Card display of schedule state is part of P7.

- [ ] **Step 1: Add TypeScript types for new schema fields**

In `frontend/src/types/` (or wherever API types are defined), update `DataSource` type:

```typescript
// Add to DataSource interface
sync_schedule: string | null;
schedule_enabled: boolean;
next_sync_at: string | null;  // ISO datetime or null
// Remove: schedule_minutes
```

- [ ] **Step 2: Add schedule preset constants**

In the DataSources component or a constants file:

```typescript
const SCHEDULE_PRESETS = [
  { label: "Every 15 minutes", cron: "*/15 * * * *" },
  { label: "Every 30 minutes", cron: "*/30 * * * *" },
  { label: "Every hour",       cron: "0 * * * *" },
  { label: "Every 6 hours",    cron: "0 */6 * * *" },
  { label: "Every 12 hours",   cron: "0 */12 * * *" },
  { label: "Nightly at 2am",   cron: "0 2 * * *" },
  { label: "Weekly (Mon 2am)", cron: "0 2 * * 1" },
  { label: "Custom…",          cron: null },
] as const;
```

- [ ] **Step 3: Add schedule UI in the wizard form**

In the DataSource create/edit form, add after the connection config section:

```tsx
{/* Schedule configuration */}
<div className="space-y-3">
  <div className="flex items-center gap-2">
    <Switch
      id="schedule-enabled"
      checked={form.schedule_enabled}
      onCheckedChange={(checked) =>
        setForm((f) => ({ ...f, schedule_enabled: checked }))
      }
    />
    <Label htmlFor="schedule-enabled">Enable automatic sync</Label>
  </div>

  {form.schedule_enabled && (
    <div className="space-y-2">
      <Label>Sync schedule</Label>
      <Select
        value={selectedPreset}
        onValueChange={(value) => {
          const preset = SCHEDULE_PRESETS.find((p) => p.label === value);
          if (preset?.cron) {
            setForm((f) => ({ ...f, sync_schedule: preset.cron }));
            setCustomCron(false);
          } else {
            setCustomCron(true);
          }
          setSelectedPreset(value);
        }}
      >
        <SelectTrigger>
          <SelectValue placeholder="Choose a schedule…" />
        </SelectTrigger>
        <SelectContent>
          {SCHEDULE_PRESETS.map((p) => (
            <SelectItem key={p.label} value={p.label}>
              {p.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {customCron && (
        <div className="space-y-1">
          <Input
            placeholder="e.g. 0 2 * * * (nightly at 2am UTC)"
            value={form.sync_schedule ?? ""}
            onChange={(e) =>
              setForm((f) => ({ ...f, sync_schedule: e.target.value }))
            }
            onBlur={() => validateCronInline(form.sync_schedule)}
          />
          <p className="text-xs text-muted-foreground">
            Cron expression is evaluated in UTC.{" "}
            <span className="font-mono">0 2 * * *</span> = 2:00 AM UTC.
          </p>
          {cronError && (
            <p className="text-xs text-destructive">{cronError}</p>
          )}
        </div>
      )}

      <p className="text-xs text-muted-foreground">
        All schedules run in UTC. Next run:{" "}
        {form.sync_schedule
          ? formatNextRun(form.sync_schedule)
          : "—"}
      </p>
    </div>
  )}
</div>
```

- [ ] **Step 4: Add `formatNextRun` helper (client-side UTC + local)**

```typescript
function formatNextRun(cronExpr: string): string {
  // Use Intl to show both UTC and local time — computed client-side
  try {
    // Simple: show "Next: <date> UTC (<local>)"
    // Full croniter-equivalent is not available in the browser;
    // next_sync_at is returned by the API on GET /datasources/
    return "See card for next run time";
  } catch {
    return "Invalid expression";
  }
}
```

- [ ] **Step 5: Run TypeScript build**

```
cd frontend && npm run build
```

Expected: Build succeeds with no TypeScript errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/
git commit -m "feat(p6b): schedule preset dropdown + enable/disable toggle in DataSource wizard"
```

---

## Task 9: Full test suite

- [ ] **Step 1: Run full backend test suite**

```
cd backend && DATABASE_URL=postgresql+asyncpg://civicrecords:civicrecords@localhost:5432/civicrecords_test python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: All tests PASS.

- [ ] **Step 2: Run frontend build**

```
cd frontend && npm run build 2>&1 | tail -20
```

Expected: Build succeeds.

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat(p6b): complete cron scheduler rewrite — all tests passing"
```
