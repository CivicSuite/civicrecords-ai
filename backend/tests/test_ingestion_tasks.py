"""Tests for sync runner connection lifecycle, logging, and Celery task decoration.

Updated for P7: run_connector_sync_with_retry (continue-on-error contract) replaces
the old run_connector_sync bare-raise loop. Tests that asserted bare-raise propagation
or cursor-held-on-partial-failure are removed — those invariants are now gone by design.
"""
import uuid
import logging
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from sqlalchemy import text

from app.models.document import DataSource, SourceType
from tests.conftest import build_data_source


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_discovered_record(n: int):
    from app.connectors.base import DiscoveredRecord
    return DiscoveredRecord(
        source_path=f"records/{n}",
        filename=f"record_{n}.json",
        file_type="json",
        file_size=10,
        metadata={},
    )


def make_fetched_document(n: int):
    from app.connectors.base import FetchedDocument
    return FetchedDocument(
        source_path=f"records/{n}",
        filename=f"record_{n}.json",
        file_type="json",
        content=b'{"id": ' + str(n).encode() + b"}",
        file_size=10,
        metadata={},
    )


async def _seed_source(db_session, source_id: uuid.UUID, name: str = "test-source"):
    user_id = (await db_session.execute(text("SELECT id FROM users LIMIT 1"))).scalar_one()
    await build_data_source(
        db_session,
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
    await db_session.commit()


# ---------------------------------------------------------------------------
# connector.close() lifecycle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_close_called_on_success(db_session):
    """Sync runner calls connector.close() in finally after a successful run."""
    source_id = uuid.uuid4()
    await _seed_source(db_session, source_id, "close-success")

    mock_connector = AsyncMock()
    mock_connector.connector_type = "rest_api"
    mock_connector.discover = AsyncMock(return_value=[make_discovered_record(1)])
    mock_connector.fetch = AsyncMock(return_value=make_fetched_document(1))
    mock_connector.close = MagicMock()

    from app.ingestion.sync_runner import run_connector_sync_with_retry
    with patch("app.ingestion.sync_runner.ingest_structured_record", new=AsyncMock(return_value=MagicMock())):
        await run_connector_sync_with_retry(
            connector=mock_connector, source_id=str(source_id), session=db_session
        )

    mock_connector.close.assert_called_once()


@pytest.mark.asyncio
async def test_close_called_on_fetch_failure(db_session):
    """Sync runner calls connector.close() even when fetch() raises (continue-on-error)."""
    source_id = uuid.uuid4()
    await _seed_source(db_session, source_id, "close-fetch-fail")

    mock_connector = AsyncMock()
    mock_connector.connector_type = "rest_api"
    mock_connector.discover = AsyncMock(return_value=[make_discovered_record(1)])
    mock_connector.fetch = AsyncMock(side_effect=RuntimeError("fetch failed"))
    mock_connector.close = MagicMock()

    from app.ingestion.sync_runner import run_connector_sync_with_retry
    # P7 contract: fetch failure does NOT propagate — it's absorbed into sync_failures
    result = await run_connector_sync_with_retry(
        connector=mock_connector, source_id=str(source_id), session=db_session
    )

    assert result["failed"] == 1
    mock_connector.close.assert_called_once()


@pytest.mark.asyncio
async def test_close_called_on_discover_failure(db_session):
    """Sync runner calls connector.close() even when discover() raises."""
    source_id = uuid.uuid4()
    await _seed_source(db_session, source_id, "close-discover-fail")

    mock_connector = AsyncMock()
    mock_connector.connector_type = "rest_api"
    mock_connector.discover = AsyncMock(side_effect=ConnectionError("IMAP down"))
    mock_connector.close = MagicMock()

    from app.ingestion.sync_runner import run_connector_sync_with_retry
    with pytest.raises(ConnectionError):
        await run_connector_sync_with_retry(
            connector=mock_connector, source_id=str(source_id), session=db_session
        )

    mock_connector.close.assert_called_once()


# ---------------------------------------------------------------------------
# Cursor semantics (P7 contract: partial-advance, not hold-all)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cursor_written_on_full_success(db_session):
    """last_sync_cursor and last_sync_at are set after a clean run."""
    from app.models.document import DataSource
    source_id = uuid.uuid4()
    await _seed_source(db_session, source_id, "cursor-success")

    mock_connector = AsyncMock()
    mock_connector.connector_type = "rest_api"
    mock_connector.discover = AsyncMock(return_value=[make_discovered_record(1)])
    mock_connector.fetch = AsyncMock(return_value=make_fetched_document(1))
    mock_connector.close = MagicMock()

    from app.ingestion.sync_runner import run_connector_sync_with_retry
    with patch("app.ingestion.sync_runner.ingest_structured_record", new=AsyncMock(return_value=MagicMock())):
        await run_connector_sync_with_retry(
            connector=mock_connector, source_id=str(source_id), session=db_session
        )

    source = await db_session.get(DataSource, source_id)
    assert source.last_sync_cursor is not None, "Cursor should be set after success"
    assert source.last_sync_at is not None, "last_sync_at should be set after success"


# ---------------------------------------------------------------------------
# Structured failure logging
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_structured_log_on_fetch_failure(db_session, caplog):
    """Failed fetch logs error_class and source info."""
    source_id = uuid.uuid4()
    await _seed_source(db_session, source_id, "log-fetch-fail")

    class CustomError(Exception):
        status_code = 503
        retry_count = 2

    mock_connector = AsyncMock()
    mock_connector.connector_type = "rest_api"
    mock_connector.discover = AsyncMock(return_value=[make_discovered_record(1)])
    mock_connector.fetch = AsyncMock(side_effect=CustomError("upstream error"))
    mock_connector.close = MagicMock()

    from app.ingestion.sync_runner import run_connector_sync_with_retry
    with caplog.at_level(logging.ERROR, logger="app.ingestion.sync_runner"):
        await run_connector_sync_with_retry(
            connector=mock_connector, source_id=str(source_id), session=db_session
        )

    assert any("Record fetch failed" in r.message for r in caplog.records), (
        "Expected 'Record fetch failed' log message"
    )


# ---------------------------------------------------------------------------
# Celery task timeout decoration
# ---------------------------------------------------------------------------

def test_task_ingest_source_has_timeouts():
    """task_ingest_source must declare soft_time_limit and time_limit."""
    from app.ingestion.tasks import task_ingest_source

    assert getattr(task_ingest_source, "soft_time_limit", None) == 3600, (
        "soft_time_limit must be 3600"
    )
    assert getattr(task_ingest_source, "time_limit", None) == 4200, (
        "time_limit must be 4200"
    )
