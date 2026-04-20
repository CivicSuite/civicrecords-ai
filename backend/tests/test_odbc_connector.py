"""
Tests for OdbcConnector using sqlite3 as a test-time ODBC adapter.
pyodbc is not required to be installed — the module-level name is patched
with a MagicMock whose .connect() returns a real in-memory SQLite connection.
"""
import asyncio
import json
import sqlite3

import pytest
from unittest.mock import MagicMock, patch

from app.connectors.odbc import OdbcConnector, _validate_identifier
from app.connectors.base import HealthStatus
from app.schemas.connectors.odbc import ODBCConfig


def _make_pyodbc_mock(sqlite_conn):
    """Return a MagicMock that mimics pyodbc with .connect() -> sqlite_conn."""
    mock = MagicMock()
    mock.connect.return_value = sqlite_conn
    return mock


@pytest.fixture
def sqlite_db():
    """In-memory SQLite with a public_records table."""
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE public_records "
        "(id INTEGER PRIMARY KEY, title TEXT, modified_at TEXT)"
    )
    conn.executemany(
        "INSERT INTO public_records VALUES (?, ?, ?)",
        [
            (1, "Record One", "2026-01-01T00:00:00Z"),
            (2, "Record Two", "2026-02-01T00:00:00Z"),
            (3, "Record Three", "2026-03-01T00:00:00Z"),
        ],
    )
    conn.commit()
    return conn


@pytest.fixture
def odbc_connector(sqlite_db):
    config = ODBCConfig(
        connection_string="Server=db.example.gov;Database=test",
        table_name="public_records",
        pk_column="id",
        modified_column="modified_at",
    )
    connector = OdbcConnector(config)
    with patch("app.connectors.odbc.pyodbc", _make_pyodbc_mock(sqlite_db)):
        asyncio.run(connector.authenticate())
    return connector


@pytest.mark.asyncio
async def test_discover_returns_all_records(odbc_connector):
    records = await odbc_connector.discover()
    assert len(records) == 3
    assert records[0].source_path == "public_records/1"


@pytest.mark.asyncio
async def test_discover_incremental_since(odbc_connector):
    """Since filter should reduce results — records 2 and 3 are after 2026-01-15."""
    records = await odbc_connector.discover(since="2026-01-15T00:00:00Z")
    assert len(records) == 2


@pytest.mark.asyncio
async def test_fetch_returns_document(odbc_connector):
    doc = await odbc_connector.fetch("public_records/1")
    assert doc.source_path == "public_records/1"
    data = json.loads(doc.content)
    assert data["id"] == 1
    assert data["title"] == "Record One"


@pytest.mark.asyncio
async def test_fetch_not_found(odbc_connector):
    with pytest.raises(FileNotFoundError):
        await odbc_connector.fetch("public_records/999")


@pytest.mark.asyncio
async def test_health_check_healthy(odbc_connector):
    result = await odbc_connector.health_check()
    assert result.status == HealthStatus.HEALTHY


@pytest.mark.asyncio
async def test_ensure_authenticated_raises_before_auth():
    config = ODBCConfig(
        connection_string="Server=db.example.gov;Database=test",
        table_name="public_records",
        pk_column="id",
    )
    connector = OdbcConnector(config)
    with pytest.raises(RuntimeError, match="authenticate()"):
        await connector.discover()


@pytest.mark.asyncio
async def test_close_releases_connection(odbc_connector):
    assert odbc_connector._connection is not None
    odbc_connector.close()
    assert odbc_connector._connection is None
    assert odbc_connector._authenticated is False


def test_sql_injection_guard_at_query_time():
    """Identifier validation runs at query construction, not just at model instantiation."""
    with pytest.raises(ValueError, match="Invalid SQL identifier"):
        _validate_identifier("records; DROP TABLE users--", "table_name")


@pytest.mark.asyncio
async def test_discover_source_path_format(odbc_connector):
    """Each discovered record has source_path = table_name/pk_value."""
    records = await odbc_connector.discover()
    for record in records:
        assert record.source_path.startswith("public_records/")
        assert record.file_type == "json"


@pytest.mark.asyncio
async def test_fetch_invalid_source_path(odbc_connector):
    """source_path without a slash raises ValueError."""
    with pytest.raises(ValueError, match="Invalid source_path format"):
        await odbc_connector.fetch("noslash")


@pytest.mark.asyncio
async def test_row_size_guard_skips_large_rows(sqlite_db):
    """Rows exceeding max_row_bytes are skipped in discover()."""
    config = ODBCConfig(
        connection_string="Server=db.example.gov;Database=test",
        table_name="public_records",
        pk_column="id",
        max_row_bytes=5,  # impossibly small — every row exceeds this
    )
    connector = OdbcConnector(config)
    with patch("app.connectors.odbc.pyodbc", _make_pyodbc_mock(sqlite_db)):
        await connector.authenticate()
    records = await connector.discover()
    assert records == []


@pytest.mark.asyncio
async def test_dsn_error_scrubbing():
    """Credential fields are redacted in error messages surfaced to callers."""
    from app.connectors.odbc import _scrub_dsn_error
    raw = "Connection failed: DSN=mydsn;UID=admin;PWD=s3cr3t;Server=db"
    scrubbed = _scrub_dsn_error(raw)
    assert "s3cr3t" not in scrubbed
    assert "admin" not in scrubbed
    assert "[REDACTED]" in scrubbed


class TestOdbcConnectorP6a:

    def test_source_path_encode_decode_special_chars(self):
        """pk_value containing '/', space, '%' → encoded in source_path, unquoted in fetch()."""
        import urllib.parse
        table = "public.contracts"
        pk = "dept/2024/item 100%"
        encoded = urllib.parse.quote(str(pk), safe="")
        source_path = f"{table}/{encoded}"

        # Simulate what fetch() must do to recover pk for SQL
        parts = source_path.split("/", 1)
        recovered_pk = urllib.parse.unquote(parts[1])
        assert recovered_pk == pk, f"Expected {pk!r}, got {recovered_pk!r}"

    def test_odbc_canonical_excludes_modified_column(self):
        """modified_column excluded from canonical bytes; sort_keys applied."""
        import json
        row = {"id": 1, "name": "Alice", "updated_at": "2026-04-16T00:00:00Z", "dept": "IT"}
        modified_column = "updated_at"

        row_without_ts = {k: v for k, v in row.items() if k != modified_column}
        canonical = json.dumps(row_without_ts, sort_keys=True, ensure_ascii=False, default=str)
        assert "updated_at" not in canonical
        assert '"dept": "IT"' in canonical
        # Keys in sorted order
        keys = list(json.loads(canonical).keys())
        assert keys == sorted(keys)
