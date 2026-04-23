# backend/tests/test_sync_runner_retry_cap.py
"""P7 per-run retry cap tests — real end-to-end calls asserting DB state."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from sqlalchemy import text

from app.models.document import DataSource, SourceType
from tests.conftest import build_data_source


async def _seed_source(session, source_id, name, **extra):
    user_id = (await session.execute(text("SELECT id FROM users LIMIT 1"))).scalar_one()
    await build_data_source(
        session,
        id=source_id,
        name=name,
        source_type=SourceType.REST_API,
        connection_config={},
        is_active=True,
        sync_schedule="0 2 * * *",
        schedule_enabled=True,
        sync_paused=False,
        consecutive_failure_count=0,
        created_by=user_id,
        **extra,
    )


@pytest.mark.asyncio
async def test_retry_cap_by_count(db_session):
    """100 retrying rows, retry_batch_size=10 → exactly 10 retried, 90 remain."""
    from app.models.sync_failure import SyncFailure
    from sqlalchemy import select, func

    source_id = uuid.uuid4()
    await _seed_source(db_session, source_id, "cap-count", retry_batch_size=10)

    for i in range(100):
        db_session.add(SyncFailure(
            source_id=source_id,
            source_path=f"https://api.example.com/records/{i}",
            error_message="err", error_class="IOError", status="retrying",
        ))
    await db_session.commit()

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

    assert fetch_call_count == 10, f"Expected 10 retries but got {fetch_call_count}"

    remaining = await db_session.scalar(
        select(func.count(SyncFailure.id)).where(
            SyncFailure.source_id == source_id,
            SyncFailure.status == "retrying",
        )
    )
    assert remaining == 90, f"Expected 90 remaining but got {remaining}"


@pytest.mark.asyncio
async def test_dead_letter_at_retry_threshold_during_retry_run(db_session):
    """A retrying row with retry_count=5 → promoted to permanently_failed, not fetched."""
    from app.models.sync_failure import SyncFailure

    source_id = uuid.uuid4()
    await _seed_source(db_session, source_id, "dead-letter-cap")

    failure = SyncFailure(
        source_id=source_id,
        source_path="https://api.example.com/records/exhausted",
        error_message="too many retries",
        error_class="IOError",
        status="retrying",
        retry_count=5,
    )
    db_session.add(failure)
    await db_session.commit()
    await db_session.refresh(failure)
    failure_id = failure.id

    mock_connector = AsyncMock()
    mock_connector.connector_type = "rest_api"
    mock_connector.discover = AsyncMock(return_value=[])
    mock_connector.fetch = AsyncMock(side_effect=AssertionError("should not be called"))
    mock_connector.close = MagicMock()

    from app.ingestion.sync_runner import run_connector_sync_with_retry
    await run_connector_sync_with_retry(
        connector=mock_connector,
        source_id=str(source_id),
        session=db_session,
    )

    row = await db_session.get(SyncFailure, failure_id)
    assert row.status == "permanently_failed"
    mock_connector.fetch.assert_not_called()
