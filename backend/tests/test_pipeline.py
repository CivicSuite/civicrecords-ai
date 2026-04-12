import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch
import uuid
import pytest

@pytest.mark.asyncio
async def test_compute_file_hash():
    from app.ingestion.pipeline import compute_file_hash
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("test content")
        f.flush()
        hash1 = compute_file_hash(Path(f.name))
        assert len(hash1) == 64
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("test content")
        f.flush()
        hash2 = compute_file_hash(Path(f.name))
        assert hash1 == hash2

@pytest.mark.asyncio
async def test_ingest_file_txt(client):
    from tests.conftest import test_session_maker
    from app.ingestion.pipeline import ingest_file
    from app.models.document import DataSource, IngestionStatus, SourceType

    mock_embeddings = [[0.1] * 768]
    with patch("app.ingestion.pipeline.embed_batch", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = mock_embeddings
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("This is a test document for ingestion.")
            f.flush()
            file_path = Path(f.name)
        async with test_session_maker() as session:
            source = DataSource(name=f"test-source-{uuid.uuid4().hex[:8]}", source_type=SourceType.UPLOAD, created_by=uuid.uuid4())
            session.add(source)
            await session.flush()
            doc = await ingest_file(session=session, file_path=file_path, source_id=source.id)
            assert doc.ingestion_status == IngestionStatus.COMPLETED
            assert doc.chunk_count >= 1
            assert doc.filename == file_path.name
            assert doc.file_type == "txt"
            mock_embed.assert_called_once()
