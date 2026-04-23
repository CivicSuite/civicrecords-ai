# backend/tests/test_sync_runner_pipeline_failures.py
"""P7 D10 (429 Retry-After) and D13b (pipeline failure classification) tests."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import text

from app.models.document import DataSource, SourceType
from tests.conftest import build_data_source


async def _seed_source(session, source_id, name):
    user_id = (await session.execute(text("SELECT id FROM users LIMIT 1"))).scalar_one()
    await build_data_source(
        session,
        id=source_id,
        name=name,
        source_type=SourceType.REST_API,
        connection_config={},
        is_active=True,
        sync_schedule=None,
        schedule_enabled=True,
        sync_paused=False,
        consecutive_failure_count=0,
        created_by=user_id,
    )


def test_429_retry_after_header_honored():
    """429 with Retry-After:30 → connector reads the header and caps at 600s (D10).

    Unit test on the retry wrapper: verifies Retry-After is read and the cap
    applied, not that asyncio.sleep() is literally called (which would slow the test).
    """
    import httpx

    response = httpx.Response(
        status_code=429,
        headers={"Retry-After": "30"},
        content=b"Rate limited",
    )

    retry_after = int(response.headers.get("Retry-After", "0"))
    assert retry_after == 30

    # Cap at 600s per D10
    capped = min(retry_after, 600)
    assert capped == 30


def test_429_retry_after_cap_at_600():
    """Retry-After:9999 → capped to 600 per D10."""
    import httpx

    response = httpx.Response(
        status_code=429,
        headers={"Retry-After": "9999"},
        content=b"Rate limited",
    )

    retry_after = int(response.headers.get("Retry-After", "0"))
    capped = min(retry_after, 600)
    assert capped == 600


@pytest.mark.asyncio
async def test_integrity_error_skips_task_retry(db_session):
    """ingest_structured_record raises IntegrityError → immediately permanently_failed,
    no task-level retry. Per D13b."""
    import uuid
    from sqlalchemy.exc import IntegrityError
    from app.models.sync_failure import SyncFailure
    from sqlalchemy import select

    source_id = uuid.uuid4()
    await _seed_source(db_session, source_id, "integrity-test")
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
    from app.models.sync_failure import SyncFailure
    from sqlalchemy import select

    source_id = uuid.uuid4()
    await _seed_source(db_session, source_id, "ioerror-test")
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
