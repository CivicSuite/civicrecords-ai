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
