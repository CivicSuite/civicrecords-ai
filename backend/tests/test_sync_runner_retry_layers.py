# backend/tests/test_sync_runner_retry_layers.py
"""P7 two-layer retry tests — real end-to-end calls into run_connector_sync_with_retry."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
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
        sync_schedule="0 2 * * *",
        schedule_enabled=True,
        sync_paused=False,
        consecutive_failure_count=0,
        created_by=user_id,
    )


@pytest.mark.asyncio
async def test_retrying_rows_processed_before_discover(db_session):
    """retrying rows in sync_failures are processed before discover() on same tick."""
    from app.models.sync_failure import SyncFailure

    source_id = uuid.uuid4()
    await _seed_source(db_session, source_id, "ordering-test")

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


@pytest.mark.asyncio
async def test_retrying_row_resolved_on_success(db_session):
    """A retrying row that fetches successfully → status=resolved, resolved_at set."""
    from app.models.sync_failure import SyncFailure
    from sqlalchemy import select

    source_id = uuid.uuid4()
    await _seed_source(db_session, source_id, "resolve-test")

    failure = SyncFailure(
        source_id=source_id,
        source_path="https://api.example.com/records/recover",
        error_message="transient",
        error_class="IOError",
        status="retrying",
        retry_count=1,
    )
    db_session.add(failure)
    failure_id = failure.id if failure.id else None
    await db_session.commit()
    await db_session.refresh(failure)
    failure_id = failure.id

    async def mock_fetch(path):
        from app.connectors.base import FetchedDocument
        return FetchedDocument(
            source_path=path, filename="x.json", file_type="json",
            content=b'{"id": 1}', file_size=9, metadata={},
        )

    mock_connector = AsyncMock()
    mock_connector.connector_type = "rest_api"
    mock_connector.authenticate = AsyncMock(return_value=True)
    mock_connector.discover = AsyncMock(return_value=[])
    mock_connector.fetch = AsyncMock(side_effect=mock_fetch)
    mock_connector.close = MagicMock()

    from app.ingestion.sync_runner import run_connector_sync_with_retry
    with patch("app.ingestion.sync_runner.ingest_structured_record", new=AsyncMock(return_value=MagicMock())):
        result = await run_connector_sync_with_retry(
            connector=mock_connector,
            source_id=str(source_id),
            session=db_session,
        )

    assert result["succeeded"] == 1

    row = await db_session.get(SyncFailure, failure_id)
    assert row.status == "resolved"
    assert row.resolved_at is not None


@pytest.mark.asyncio
async def test_retrying_row_increments_retry_count_on_failure(db_session):
    """A retrying row that fails again → retry_count incremented, status remains retrying."""
    from app.models.sync_failure import SyncFailure

    source_id = uuid.uuid4()
    await _seed_source(db_session, source_id, "retry-count-test")

    failure = SyncFailure(
        source_id=source_id,
        source_path="https://api.example.com/records/flaky",
        error_message="original error",
        error_class="IOError",
        status="retrying",
        retry_count=2,
    )
    db_session.add(failure)
    await db_session.commit()
    await db_session.refresh(failure)
    failure_id = failure.id

    mock_connector = AsyncMock()
    mock_connector.connector_type = "rest_api"
    mock_connector.authenticate = AsyncMock(return_value=True)
    mock_connector.discover = AsyncMock(return_value=[])
    mock_connector.fetch = AsyncMock(side_effect=RuntimeError("still failing"))
    mock_connector.close = MagicMock()

    from app.ingestion.sync_runner import run_connector_sync_with_retry
    await run_connector_sync_with_retry(
        connector=mock_connector,
        source_id=str(source_id),
        session=db_session,
    )

    row = await db_session.get(SyncFailure, failure_id)
    assert row.retry_count == 3
    assert row.status == "retrying"
    assert row.last_retried_at is not None
