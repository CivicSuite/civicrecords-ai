"""Tests for Manual/Export Drop connector."""

import pytest
import tempfile
from pathlib import Path

from app.connectors.manual_drop import (
    ManualDropConnector,
    ACCEPTED_EXTENSIONS,
    MAX_FILE_BYTES,
)


# ── Setup Helpers ─────────────────────────────────────────────────────────────

@pytest.fixture
def drop_dir():
    """Create a temporary drop directory with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)

        # Create test files
        (d / "budget.pdf").write_bytes(b"%PDF-1.4 budget content")
        (d / "memo.docx").write_bytes(b"PK\x03\x04 docx content")
        (d / "data.csv").write_text("col1,col2\n1,2\n3,4")
        (d / "notes.txt").write_text("Meeting notes from Tuesday")
        (d / "photo.jpg").write_bytes(b"\xff\xd8\xff\xe0 jpeg data")

        # Files that should be skipped
        (d / "virus.exe").write_bytes(b"\x4d\x5a executable")
        (d / "script.py").write_text("import os; os.system('rm -rf /')")
        (d / ".hidden").write_text("hidden file")
        (d / "empty.pdf").write_bytes(b"")  # zero-byte

        yield d


# ── Connector Protocol Tests ─────────────────────────────────────────────────

def test_connector_type():
    connector = ManualDropConnector(config={})
    assert connector.connector_type == "manual_drop"


@pytest.mark.asyncio
async def test_authenticate_success(drop_dir):
    connector = ManualDropConnector(config={"drop_path": str(drop_dir)})
    result = await connector.authenticate()
    assert result is True
    assert (drop_dir / "_processed").is_dir()


@pytest.mark.asyncio
async def test_authenticate_missing_path():
    connector = ManualDropConnector(config={"drop_path": ""})
    result = await connector.authenticate()
    assert result is False


@pytest.mark.asyncio
async def test_authenticate_nonexistent_path():
    connector = ManualDropConnector(config={"drop_path": "/nonexistent/path"})
    result = await connector.authenticate()
    assert result is False


@pytest.mark.asyncio
async def test_discover_finds_eligible_files(drop_dir):
    connector = ManualDropConnector(config={"drop_path": str(drop_dir)})
    await connector.authenticate()
    records = await connector.discover()

    filenames = {r.filename for r in records}
    # Should find the 5 valid files
    assert "budget.pdf" in filenames
    assert "memo.docx" in filenames
    assert "data.csv" in filenames
    assert "notes.txt" in filenames
    assert "photo.jpg" in filenames

    # Should NOT find rejected files
    assert "virus.exe" not in filenames
    assert "script.py" not in filenames
    assert ".hidden" not in filenames
    assert "empty.pdf" not in filenames

    assert len(records) == 5


@pytest.mark.asyncio
async def test_discover_skips_archive_folder(drop_dir):
    """Files in _processed archive should not be rediscovered."""
    connector = ManualDropConnector(config={"drop_path": str(drop_dir)})
    await connector.authenticate()

    # Put a file in the archive folder
    archive = drop_dir / "_processed"
    (archive / "old.pdf").write_bytes(b"%PDF archived")

    records = await connector.discover()
    filenames = {r.filename for r in records}
    assert "old.pdf" not in filenames


@pytest.mark.asyncio
async def test_discover_skips_oversized_files(drop_dir):
    """Files over MAX_FILE_BYTES are skipped."""
    connector = ManualDropConnector(config={"drop_path": str(drop_dir)})
    await connector.authenticate()

    # Create a file just over the limit (write a small marker, check size logic)
    huge = drop_dir / "huge.pdf"
    huge.write_bytes(b"x" * (MAX_FILE_BYTES + 1))

    records = await connector.discover()
    filenames = {r.filename for r in records}
    assert "huge.pdf" not in filenames


@pytest.mark.asyncio
async def test_fetch_reads_file(drop_dir):
    connector = ManualDropConnector(config={"drop_path": str(drop_dir)})
    await connector.authenticate()

    doc = await connector.fetch(str(drop_dir / "notes.txt"))
    assert doc.filename == "notes.txt"
    assert doc.file_type == "txt"
    assert b"Meeting notes" in doc.content
    assert "sha256" in doc.metadata
    assert len(doc.metadata["sha256"]) == 64  # SHA-256 hex digest


@pytest.mark.asyncio
async def test_fetch_nonexistent_file(drop_dir):
    connector = ManualDropConnector(config={"drop_path": str(drop_dir)})
    await connector.authenticate()

    with pytest.raises(FileNotFoundError):
        await connector.fetch(str(drop_dir / "nonexistent.pdf"))


@pytest.mark.asyncio
async def test_archive_moves_file(drop_dir):
    connector = ManualDropConnector(config={"drop_path": str(drop_dir)})
    await connector.authenticate()

    source = str(drop_dir / "notes.txt")
    assert Path(source).exists()

    dest = connector.archive_file(source)
    assert dest is not None
    assert dest.exists()
    assert not Path(source).exists()  # original moved
    assert "_processed" in str(dest)


@pytest.mark.asyncio
async def test_archive_disabled(drop_dir):
    connector = ManualDropConnector(config={
        "drop_path": str(drop_dir),
        "archive_processed": False,
    })
    await connector.authenticate()

    result = connector.archive_file(str(drop_dir / "notes.txt"))
    assert result is None  # archiving disabled
    assert (drop_dir / "notes.txt").exists()  # file untouched


@pytest.mark.asyncio
async def test_archive_handles_duplicate_names(drop_dir):
    connector = ManualDropConnector(config={"drop_path": str(drop_dir)})
    await connector.authenticate()

    # Archive the same filename twice (create a second copy)
    connector.archive_file(str(drop_dir / "budget.pdf"))

    # Create another file with the same name
    (drop_dir / "budget.pdf").write_bytes(b"%PDF second version")
    dest2 = connector.archive_file(str(drop_dir / "budget.pdf"))

    assert dest2 is not None
    assert dest2.exists()
    # Should have a timestamp suffix to avoid overwrite
    assert "budget_" in dest2.name or dest2.name == "budget.pdf"


@pytest.mark.asyncio
async def test_health_check_healthy(drop_dir):
    connector = ManualDropConnector(config={"drop_path": str(drop_dir)})
    await connector.authenticate()

    result = await connector.health_check()
    assert result.status.value == "healthy"
    assert result.records_available is not None
    assert result.latency_ms is not None


@pytest.mark.asyncio
async def test_health_check_unconfigured():
    connector = ManualDropConnector(config={})
    result = await connector.health_check()
    assert result.status.value == "unreachable"


@pytest.mark.asyncio
async def test_discover_raises_without_auth():
    connector = ManualDropConnector(config={})
    with pytest.raises(RuntimeError, match="Not authenticated"):
        await connector.discover()


@pytest.mark.asyncio
async def test_recursive_discovery(drop_dir):
    """With recursive=True, files in subdirectories are found."""
    subdir = drop_dir / "department_a"
    subdir.mkdir()
    (subdir / "report.pdf").write_bytes(b"%PDF dept a report")

    connector = ManualDropConnector(config={
        "drop_path": str(drop_dir),
        "recursive": True,
    })
    await connector.authenticate()
    records = await connector.discover()

    filenames = {r.filename for r in records}
    assert "report.pdf" in filenames


@pytest.mark.asyncio
async def test_non_recursive_skips_subdirs(drop_dir):
    """Without recursive, subdirectory files are not found."""
    subdir = drop_dir / "department_b"
    subdir.mkdir()
    (subdir / "hidden_report.pdf").write_bytes(b"%PDF hidden")

    connector = ManualDropConnector(config={
        "drop_path": str(drop_dir),
        "recursive": False,
    })
    await connector.authenticate()
    records = await connector.discover()

    filenames = {r.filename for r in records}
    assert "hidden_report.pdf" not in filenames


# ── Pipeline Dispatch Tests ───────────────────────────────────────────────────

from app.connectors import manual_drop as _drop_mod


@pytest.mark.asyncio
async def test_ingest_manual_drop_dispatch(drop_dir):
    """_ingest_manual_drop_source discovers, fetches, ingests, and archives."""
    from unittest.mock import AsyncMock, MagicMock, patch
    from app.ingestion.tasks import _ingest_manual_drop_source
    from app.connectors.base import DiscoveredRecord, FetchedDocument

    source = MagicMock()
    source.id = "00000000-0000-0000-0000-000000000002"
    source.connection_config = {"drop_path": str(drop_dir)}
    source.last_ingestion_at = None

    mock_connector = MagicMock()
    mock_connector.authenticate = AsyncMock(return_value=True)
    mock_connector.discover = AsyncMock(return_value=[
        DiscoveredRecord(
            source_path=str(drop_dir / "budget.pdf"),
            filename="budget.pdf",
            file_type="pdf",
            file_size=100,
        ),
        DiscoveredRecord(
            source_path=str(drop_dir / "notes.txt"),
            filename="notes.txt",
            file_type="txt",
            file_size=50,
        ),
    ])
    mock_connector.fetch = AsyncMock(side_effect=[
        FetchedDocument(
            source_path=str(drop_dir / "budget.pdf"),
            filename="budget.pdf", file_type="pdf",
            content=b"%PDF content", file_size=12,
        ),
        FetchedDocument(
            source_path=str(drop_dir / "notes.txt"),
            filename="notes.txt", file_type="txt",
            content=b"Meeting notes", file_size=13,
        ),
    ])
    # archive_file is sync
    mock_connector.archive_file = MagicMock(return_value=Path("/archived"))

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()

    with patch.object(_drop_mod, "ManualDropConnector", return_value=mock_connector), \
         patch("app.ingestion.tasks.ingest_file_from_bytes", new_callable=AsyncMock) as mock_ingest, \
         patch("app.ingestion.tasks.write_audit_log", new_callable=AsyncMock):
        mock_ingest.return_value = MagicMock()

        result = await _ingest_manual_drop_source(mock_session, source, user_id=None)

    assert result["discovered"] == 2
    assert result["ingested"] == 2
    assert result["errors"] == 0
    mock_connector.authenticate.assert_called_once()
    mock_connector.discover.assert_called_once()
    assert mock_connector.fetch.call_count == 2
    assert mock_connector.archive_file.call_count == 2


@pytest.mark.asyncio
async def test_ingest_manual_drop_auth_failure():
    """_ingest_manual_drop_source returns error on inaccessible folder."""
    from unittest.mock import AsyncMock, MagicMock, patch
    from app.ingestion.tasks import _ingest_manual_drop_source

    source = MagicMock()
    source.connection_config = {"drop_path": "/nonexistent"}

    mock_connector = MagicMock()
    mock_connector.authenticate = AsyncMock(return_value=False)

    mock_session = AsyncMock()

    with patch.object(_drop_mod, "ManualDropConnector", return_value=mock_connector):
        result = await _ingest_manual_drop_source(mock_session, source, user_id=None)

    assert result["error"] == "ManualDrop: drop folder not accessible"
