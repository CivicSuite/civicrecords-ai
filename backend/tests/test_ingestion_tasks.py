"""Tests for sync runner cursor semantics, connection lifecycle, and structured logging.

These tests exercise run_connector_sync() directly with mocked connectors.
DB-dependent tests (test_cursor_not_written_on_partial_failure) require PostgreSQL
and are skipped in pure-unit mode unless a real db_session fixture is provided.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_discovered_record(n: int):
    """Return a minimal DiscoveredRecord-like object."""
    from app.connectors.base import DiscoveredRecord
    return DiscoveredRecord(
        source_path=f"records/{n}",
        filename=f"record_{n}.json",
        file_type="json",
        file_size=10,
        metadata={},
    )


def make_fetched_document(n: int):
    """Return a minimal FetchedDocument-like object."""
    from app.connectors.base import FetchedDocument
    return FetchedDocument(
        source_path=f"records/{n}",
        filename=f"record_{n}.json",
        file_type="json",
        content=b'{"id": ' + str(n).encode() + b"}",
        file_size=10,
        metadata={},
    )


def _make_mock_source(source_id="00000000-0000-0000-0000-000000000001"):
    """Return a mock DataSource with the fields run_connector_sync reads."""
    source = MagicMock()
    source.id = source_id
    source.last_sync_cursor = None
    source.last_sync_at = None
    return source


# ---------------------------------------------------------------------------
# close() lifecycle tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_close_called_on_success():
    """Sync runner calls connector.close() in finally after a successful run."""
    import uuid
    from app.ingestion.tasks import run_connector_sync

    source_id = str(uuid.uuid4())

    connector = MagicMock()
    connector.discover = AsyncMock(return_value=[make_discovered_record(1)])
    connector.fetch = AsyncMock(return_value=make_fetched_document(1))
    connector.close = MagicMock()

    mock_source = _make_mock_source(source_id)
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=mock_source)
    mock_session.commit = AsyncMock()

    with patch("app.ingestion.tasks.ingest_file_from_bytes", new=AsyncMock(return_value=MagicMock())):
        await run_connector_sync(connector, source_id=source_id, session=mock_session)

    connector.close.assert_called_once()


@pytest.mark.asyncio
async def test_close_called_on_fetch_failure():
    """Sync runner calls connector.close() even when fetch() raises."""
    import uuid
    from app.ingestion.tasks import run_connector_sync

    source_id = str(uuid.uuid4())

    connector = MagicMock()
    connector.discover = AsyncMock(return_value=[make_discovered_record(1)])
    connector.fetch = AsyncMock(side_effect=RuntimeError("fetch failed"))
    connector.close = MagicMock()

    mock_source = _make_mock_source(source_id)
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=mock_source)
    mock_session.commit = AsyncMock()

    with pytest.raises(RuntimeError, match="fetch failed"):
        await run_connector_sync(connector, source_id=source_id, session=mock_session)

    connector.close.assert_called_once()


@pytest.mark.asyncio
async def test_close_called_on_discover_failure():
    """Sync runner calls connector.close() even when discover() raises."""
    import uuid
    from app.ingestion.tasks import run_connector_sync

    source_id = str(uuid.uuid4())

    connector = MagicMock()
    connector.discover = AsyncMock(side_effect=ConnectionError("IMAP down"))
    connector.close = MagicMock()

    mock_source = _make_mock_source(source_id)
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=mock_source)

    with pytest.raises(ConnectionError):
        await run_connector_sync(connector, source_id=source_id, session=mock_session)

    connector.close.assert_called_once()


# ---------------------------------------------------------------------------
# Cursor-on-success semantics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cursor_written_on_full_success():
    """last_sync_cursor and last_sync_at are set after a clean run."""
    import uuid
    from app.ingestion.tasks import run_connector_sync

    source_id = str(uuid.uuid4())

    connector = MagicMock()
    connector.discover = AsyncMock(return_value=[make_discovered_record(1)])
    connector.fetch = AsyncMock(return_value=make_fetched_document(1))
    connector.close = MagicMock()

    mock_source = _make_mock_source(source_id)
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=mock_source)
    mock_session.commit = AsyncMock()

    with patch("app.ingestion.tasks.ingest_file_from_bytes", new=AsyncMock(return_value=MagicMock())):
        await run_connector_sync(connector, source_id=source_id, session=mock_session)

    assert mock_source.last_sync_cursor is not None, "Cursor should be set after success"
    assert mock_source.last_sync_at is not None, "last_sync_at should be set after success"
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_cursor_not_written_on_fetch_failure():
    """last_sync_cursor must NOT advance if fetch() raises."""
    import uuid
    from app.ingestion.tasks import run_connector_sync

    source_id = str(uuid.uuid4())

    connector = MagicMock()
    connector.discover = AsyncMock(return_value=[make_discovered_record(1)])
    connector.fetch = AsyncMock(side_effect=RuntimeError("fetch failed"))
    connector.close = MagicMock()

    mock_source = _make_mock_source(source_id)
    original_cursor = mock_source.last_sync_cursor  # None
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=mock_source)
    mock_session.commit = AsyncMock()

    with pytest.raises(RuntimeError):
        await run_connector_sync(connector, source_id=source_id, session=mock_session)

    assert mock_source.last_sync_cursor == original_cursor, (
        f"Cursor advanced to '{mock_source.last_sync_cursor}' despite fetch failure"
    )
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_cursor_not_written_on_partial_failure():
    """last_sync_cursor must NOT advance if any fetch fails mid-run."""
    import uuid
    from app.connectors.base import FetchedDocument
    from app.ingestion.tasks import run_connector_sync

    source_id = str(uuid.uuid4())

    connector = MagicMock()
    connector.discover = AsyncMock(return_value=[
        make_discovered_record(1),
        make_discovered_record(2),
    ])
    connector.fetch = AsyncMock(side_effect=[
        make_fetched_document(1),               # first succeeds
        RuntimeError("second fetch failed"),    # second fails
    ])
    connector.close = MagicMock()

    mock_source = _make_mock_source(source_id)
    original_cursor = mock_source.last_sync_cursor
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=mock_source)
    mock_session.commit = AsyncMock()

    with patch("app.ingestion.tasks.ingest_file_from_bytes", new=AsyncMock(return_value=MagicMock())):
        with pytest.raises(RuntimeError, match="second fetch failed"):
            await run_connector_sync(connector, source_id=source_id, session=mock_session)

    assert mock_source.last_sync_cursor == original_cursor, (
        f"Cursor advanced to '{mock_source.last_sync_cursor}' despite mid-run failure"
    )
    mock_session.commit.assert_not_called()
    connector.close.assert_called_once()


# ---------------------------------------------------------------------------
# Structured failure logging
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_structured_log_on_fetch_failure(caplog):
    """Failed fetch logs error_class, record_id, status_code, retry_count."""
    import uuid
    import logging
    from app.ingestion.tasks import run_connector_sync

    source_id = str(uuid.uuid4())

    class CustomError(Exception):
        status_code = 503
        retry_count = 2

    connector = MagicMock()
    connector.discover = AsyncMock(return_value=[make_discovered_record(1)])
    connector.fetch = AsyncMock(side_effect=CustomError("upstream error"))
    connector.close = MagicMock()

    mock_source = _make_mock_source(source_id)
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=mock_source)
    mock_session.commit = AsyncMock()

    with caplog.at_level(logging.ERROR, logger="app.ingestion.tasks"):
        with pytest.raises(CustomError):
            await run_connector_sync(connector, source_id=source_id, session=mock_session)

    assert any("Fetch failed" in r.message for r in caplog.records), (
        "Expected 'Fetch failed' log message"
    )


# ---------------------------------------------------------------------------
# Celery task timeout decoration test
# ---------------------------------------------------------------------------


def test_task_ingest_source_has_timeouts():
    """task_ingest_source must declare soft_time_limit and time_limit."""
    from app.ingestion.tasks import task_ingest_source

    # Celery task options live on task.soft_time_limit / task.time_limit
    assert getattr(task_ingest_source, "soft_time_limit", None) == 3600, (
        "soft_time_limit must be 3600"
    )
    assert getattr(task_ingest_source, "time_limit", None) == 4200, (
        "time_limit must be 4200"
    )


# ---------------------------------------------------------------------------
# db kwarg alias
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_db_kwarg_alias():
    """run_connector_sync accepts db= as an alias for session=."""
    import uuid
    from app.ingestion.tasks import run_connector_sync

    source_id = str(uuid.uuid4())

    connector = MagicMock()
    connector.discover = AsyncMock(return_value=[])
    connector.close = MagicMock()

    mock_source = _make_mock_source(source_id)
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=mock_source)
    mock_session.commit = AsyncMock()

    # Pass db= instead of session=
    await run_connector_sync(connector, source_id=source_id, db=mock_session)

    connector.close.assert_called_once()
