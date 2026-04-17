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

    async def _seed_user(self, db_session):
        from sqlalchemy import text
        await db_session.execute(text("""
            INSERT INTO users (id, email, hashed_password, full_name, role, is_active, is_superuser, is_verified)
            VALUES ('00000000-0000-0000-0000-000000000001', 'seed@test.local', 'x', 'Seed', 'admin', true, true, true)
            ON CONFLICT (id) DO NOTHING
        """))
        await db_session.commit()

    @pytest.mark.asyncio
    async def test_schedule_disabled_not_triggered(self, db_session):
        """Source with valid cron but schedule_enabled=False → not triggered."""
        from app.ingestion.scheduler import _check_scheduled_sources_async
        await self._seed_user(db_session)
        source_id = uuid.uuid4()
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

        with patch("app.ingestion.tasks.task_ingest_source") as mock_task:
            await _check_scheduled_sources_async(db_session)
            mock_task.delay.assert_not_called()

    @pytest.mark.asyncio
    async def test_paused_source_not_triggered(self, db_session):
        """Source with valid cron but sync_paused=True → not triggered."""
        from app.ingestion.scheduler import _check_scheduled_sources_async
        await self._seed_user(db_session)
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

        with patch("app.ingestion.tasks.task_ingest_source") as mock_task:
            await _check_scheduled_sources_async(db_session)
            mock_task.delay.assert_not_called()
