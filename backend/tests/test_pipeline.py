import tempfile
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

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
async def test_ingest_file_txt(client, admin_token):
    """Integration test: ingest a text file through the full pipeline."""
    from tests.conftest import test_session_maker
    from app.ingestion.pipeline import ingest_file
    from app.models.document import DataSource, Document, IngestionStatus, SourceType
    from app.models.user import User
    from sqlalchemy import select

    mock_embeddings = [[0.1] * 768]
    with patch("app.ingestion.pipeline.embed_batch", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = mock_embeddings
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("This is a test document for ingestion.")
            f.flush()
            file_path = Path(f.name)
        async with test_session_maker() as session:
            # Get a real user ID from the database
            result = await session.execute(select(User).limit(1))
            user = result.scalar_one()

            source = DataSource(
                name=f"test-source-{uuid.uuid4().hex[:8]}",
                source_type=SourceType.MANUAL_DROP,
                created_by=user.id,
            )
            session.add(source)
            await session.flush()
            doc = await ingest_file(session=session, file_path=file_path, source_id=source.id)
            assert doc.ingestion_status == IngestionStatus.COMPLETED
            assert doc.chunk_count >= 1
            assert doc.filename == file_path.name
            assert doc.file_type == "txt"
            mock_embed.assert_called_once()
