# backend/tests/test_circuit_breaker.py
"""P7 circuit breaker tests — real end-to-end calls asserting DB state."""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


UTC = timezone.utc


@pytest.mark.asyncio
async def test_circuit_opens_after_5_consecutive_full_run_failures(db_session):
    """5 consecutive all-fail runs → sync_paused=True, consecutive_failure_count=5."""
    from app.models.document import DataSource
    from app.connectors.base import DiscoveredRecord
    from sqlalchemy import text

    source_id = uuid.uuid4()
    await db_session.execute(text("""
        INSERT INTO data_sources
          (id, name, source_type, connection_config, is_active,
           sync_schedule, schedule_enabled, sync_paused,
           consecutive_failure_count, created_by)
        VALUES (:id, 'circuit-open', 'rest_api', '{}', true,
                '0 2 * * *', true, false, 0,
                (SELECT id FROM users LIMIT 1))
    """), {"id": str(source_id)})
    await db_session.commit()

    discovered = [
        DiscoveredRecord(source_path="https://api.example.com/records/1",
                         filename="1.json", file_type="json", file_size=10),
    ]

    mock_connector = AsyncMock()
    mock_connector.connector_type = "rest_api"
    mock_connector.discover = AsyncMock(return_value=discovered)
    mock_connector.fetch = AsyncMock(side_effect=IOError("network down"))
    mock_connector.close = MagicMock()

    from app.ingestion.sync_runner import run_connector_sync_with_retry

    for _ in range(5):
        mock_connector.close = MagicMock()
        await run_connector_sync_with_retry(
            connector=mock_connector,
            source_id=str(source_id),
            session=db_session,
        )

    source = await db_session.get(DataSource, source_id)
    assert source.consecutive_failure_count == 5
    assert source.sync_paused is True


@pytest.mark.asyncio
async def test_circuit_does_not_open_at_4_failures(db_session):
    """4 consecutive all-fail runs → sync_paused=False, counter=4."""
    from app.models.document import DataSource
    from app.connectors.base import DiscoveredRecord
    from sqlalchemy import text

    source_id = uuid.uuid4()
    await db_session.execute(text("""
        INSERT INTO data_sources
          (id, name, source_type, connection_config, is_active,
           sync_schedule, schedule_enabled, sync_paused,
           consecutive_failure_count, created_by)
        VALUES (:id, 'circuit-no-open', 'rest_api', '{}', true,
                '0 2 * * *', true, false, 0,
                (SELECT id FROM users LIMIT 1))
    """), {"id": str(source_id)})
    await db_session.commit()

    discovered = [
        DiscoveredRecord(source_path="https://api.example.com/records/1",
                         filename="1.json", file_type="json", file_size=10),
    ]

    mock_connector = AsyncMock()
    mock_connector.connector_type = "rest_api"
    mock_connector.discover = AsyncMock(return_value=discovered)
    mock_connector.fetch = AsyncMock(side_effect=IOError("network down"))
    mock_connector.close = MagicMock()

    from app.ingestion.sync_runner import run_connector_sync_with_retry

    for _ in range(4):
        mock_connector.close = MagicMock()
        await run_connector_sync_with_retry(
            connector=mock_connector,
            source_id=str(source_id),
            session=db_session,
        )

    source = await db_session.get(DataSource, source_id)
    assert source.consecutive_failure_count == 4
    assert source.sync_paused is False


@pytest.mark.asyncio
async def test_success_resets_consecutive_failure_count(db_session):
    """3 failures then 1 success → consecutive_failure_count=0, sync_paused=False."""
    from app.models.document import DataSource
    from app.connectors.base import DiscoveredRecord, FetchedDocument
    from sqlalchemy import text

    source_id = uuid.uuid4()
    await db_session.execute(text("""
        INSERT INTO data_sources
          (id, name, source_type, connection_config, is_active,
           sync_schedule, schedule_enabled, sync_paused,
           consecutive_failure_count, created_by)
        VALUES (:id, 'circuit-reset', 'rest_api', '{}', true,
                '0 2 * * *', true, false, 3,
                (SELECT id FROM users LIMIT 1))
    """), {"id": str(source_id)})
    await db_session.commit()

    discovered = [
        DiscoveredRecord(source_path="https://api.example.com/records/1",
                         filename="1.json", file_type="json", file_size=10),
    ]

    mock_connector = AsyncMock()
    mock_connector.connector_type = "rest_api"
    mock_connector.discover = AsyncMock(return_value=discovered)
    mock_connector.fetch = AsyncMock(return_value=FetchedDocument(
        source_path="https://api.example.com/records/1",
        filename="1.json", file_type="json", content=b'{"id":1}', file_size=7, metadata={},
    ))
    mock_connector.close = MagicMock()

    from app.ingestion.sync_runner import run_connector_sync_with_retry
    with patch("app.ingestion.sync_runner.ingest_structured_record", new=AsyncMock(return_value=MagicMock())):
        await run_connector_sync_with_retry(
            connector=mock_connector,
            source_id=str(source_id),
            session=db_session,
        )

    source = await db_session.get(DataSource, source_id)
    assert source.consecutive_failure_count == 0
    assert source.sync_paused is False


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
    """0 new records discovered, but retrying rows succeed → counter resets to 0 (D-FAIL-4)."""
    from app.models.document import DataSource
    from app.models.sync_failure import SyncFailure
    import uuid
    from sqlalchemy import text
    from app.connectors.base import FetchedDocument

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
    await db_session.refresh(failure)
    failure_id = failure.id

    mock_connector = AsyncMock()
    mock_connector.connector_type = "rest_api"
    mock_connector.discover = AsyncMock(return_value=[])  # 0 new records
    mock_connector.fetch = AsyncMock(return_value=FetchedDocument(
        source_path="https://api.example.com/records/retry-me",
        filename="retry-me.json", file_type="json",
        content=b'{"id":1}', file_size=7, metadata={},
    ))
    mock_connector.close = MagicMock()

    from app.ingestion.sync_runner import run_connector_sync_with_retry
    with patch("app.ingestion.sync_runner.ingest_structured_record", new=AsyncMock(return_value=MagicMock())):
        await run_connector_sync_with_retry(
            connector=mock_connector,
            source_id=str(source_id),
            session=db_session,
        )

    source = await db_session.get(DataSource, source_id)
    assert source.consecutive_failure_count == 0
    assert source.sync_paused is False

    row = await db_session.get(SyncFailure, failure_id)
    assert row.status == "resolved"


# ---------------------------------------------------------------------------
# P7 adversarial — grace period re-pause path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_grace_period_trips_circuit_at_2_failures_not_5(db_session):
    """After admin unpauses (grace_period sentinel), 2 consecutive all-fail runs
    must re-pause the source — NOT 5 (the normal threshold).

    This verifies the grace-period fast-feedback path: admins know within 2
    sync ticks if their fix didn't work, instead of waiting for 5 more failures.
    """
    from app.models.document import DataSource
    from app.connectors.base import DiscoveredRecord
    from sqlalchemy import text

    source_id = uuid.uuid4()
    # Simulate a source that was just unpaused — consecutive_failure_count=0,
    # sync_paused=False, sync_paused_reason="grace_period" (set by /unpause endpoint).
    await db_session.execute(text("""
        INSERT INTO data_sources
          (id, name, source_type, connection_config, is_active,
           sync_schedule, schedule_enabled, sync_paused,
           consecutive_failure_count, sync_paused_reason, created_by)
        VALUES (:id, 'grace-reopen', 'rest_api', '{}', true,
                '0 2 * * *', true, false, 0, 'grace_period',
                (SELECT id FROM users LIMIT 1))
    """), {"id": str(source_id)})
    await db_session.commit()

    discovered = [
        DiscoveredRecord(source_path="https://api.example.com/records/1",
                         filename="1.json", file_type="json", file_size=10),
    ]

    mock_connector = AsyncMock()
    mock_connector.connector_type = "rest_api"
    mock_connector.discover = AsyncMock(return_value=discovered)
    mock_connector.fetch = AsyncMock(side_effect=IOError("still broken"))
    mock_connector.close = MagicMock()

    from app.ingestion.sync_runner import run_connector_sync_with_retry

    # First failure — counter becomes 1, threshold=2, not yet tripped
    await run_connector_sync_with_retry(
        connector=mock_connector,
        source_id=str(source_id),
        session=db_session,
    )
    source = await db_session.get(DataSource, source_id)
    assert source.sync_paused is False, "Should NOT be paused after only 1 grace-period failure"
    assert source.consecutive_failure_count == 1

    # Second failure — counter becomes 2, threshold=2, circuit opens
    mock_connector.close = MagicMock()
    await run_connector_sync_with_retry(
        connector=mock_connector,
        source_id=str(source_id),
        session=db_session,
    )
    source = await db_session.get(DataSource, source_id)
    assert source.sync_paused is True, "Grace period exhausted: should be re-paused after 2 failures"
    assert source.consecutive_failure_count == 2


@pytest.mark.asyncio
async def test_grace_period_clears_on_success(db_session):
    """After unpause (grace_period sentinel), a successful sync clears the sentinel
    so the source returns to normal 5-failure threshold.
    """
    from app.models.document import DataSource
    from app.connectors.base import DiscoveredRecord, FetchedDocument
    from sqlalchemy import text

    source_id = uuid.uuid4()
    await db_session.execute(text("""
        INSERT INTO data_sources
          (id, name, source_type, connection_config, is_active,
           sync_schedule, schedule_enabled, sync_paused,
           consecutive_failure_count, sync_paused_reason, created_by)
        VALUES (:id, 'grace-clear', 'rest_api', '{}', true,
                '0 2 * * *', true, false, 0, 'grace_period',
                (SELECT id FROM users LIMIT 1))
    """), {"id": str(source_id)})
    await db_session.commit()

    discovered = [
        DiscoveredRecord(source_path="https://api.example.com/records/1",
                         filename="1.json", file_type="json", file_size=10),
    ]

    mock_connector = AsyncMock()
    mock_connector.connector_type = "rest_api"
    mock_connector.discover = AsyncMock(return_value=discovered)
    mock_connector.fetch = AsyncMock(return_value=FetchedDocument(
        source_path="https://api.example.com/records/1",
        filename="1.json", file_type="json", content=b'{"id":1}', file_size=7, metadata={},
    ))
    mock_connector.close = MagicMock()

    from app.ingestion.sync_runner import run_connector_sync_with_retry
    with patch("app.ingestion.sync_runner.ingest_structured_record", new=AsyncMock(return_value=MagicMock())):
        await run_connector_sync_with_retry(
            connector=mock_connector,
            source_id=str(source_id),
            session=db_session,
        )

    source = await db_session.get(DataSource, source_id)
    assert source.sync_paused is False
    assert source.consecutive_failure_count == 0
    # Grace sentinel must be cleared — normal 5-failure threshold restored
    assert source.sync_paused_reason is None
