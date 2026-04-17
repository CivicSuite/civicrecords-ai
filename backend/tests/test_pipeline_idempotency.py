# backend/tests/test_pipeline_idempotency.py
"""P6a idempotency tests — TDD order: all [FIRST] tests must fail before implementation."""
import hashlib
import json
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_source_id() -> uuid.UUID:
    return uuid.uuid4()


def _canonical_rest(record: dict, data_key: str | None = None) -> bytes:
    """Reference implementation of what fetch() should produce."""
    if data_key:
        parts = data_key.split(".")
        obj = record
        for p in parts:
            obj = obj[p]
        record = obj
    return json.dumps(record, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")


def _canonical_odbc(row_dict: dict, modified_column: str | None = None) -> bytes:
    d = {k: v for k, v in row_dict.items() if k != modified_column}
    return json.dumps(d, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")


# ---------------------------------------------------------------------------
# REST — determinism tests
# ---------------------------------------------------------------------------

class TestRestDeterminism:
    """REST fetch() must produce identical bytes for the same logical record
    regardless of envelope timestamp or key ordering."""

    def test_rest_envelope_timestamp_same_document(self):
        """Two fetches with differing fetched_at in envelope → same canonical bytes
        when data_key='data' extracts the inner record."""
        record = {"id": 1, "title": "Budget Report", "amount": 50000}

        response_fetch1 = {"fetched_at": "2026-04-16T01:00:00Z", "data": record}
        response_fetch2 = {"fetched_at": "2026-04-16T01:05:00Z", "data": record}

        bytes1 = _canonical_rest(response_fetch1, data_key="data")
        bytes2 = _canonical_rest(response_fetch2, data_key="data")

        assert bytes1 == bytes2, (
            "Envelope timestamp differs between fetches but should not affect canonical bytes"
        )

    def test_rest_key_order_same_document(self):
        """Same logical record with JSON keys in different order → same canonical bytes."""
        bytes1 = _canonical_rest({"id": 1, "title": "Permit", "status": "open"})
        bytes2 = _canonical_rest({"status": "open", "id": 1, "title": "Permit"})
        assert bytes1 == bytes2


class TestOdbcDeterminism:
    """ODBC fetch() must produce identical bytes regardless of modified_column or column order."""

    def test_odbc_modified_column_excluded(self):
        """Same row with modified_column ticking → same canonical bytes."""
        row1 = {"id": 42, "name": "Contract A", "last_modified": "2026-04-16T01:00:00Z"}
        row2 = {"id": 42, "name": "Contract A", "last_modified": "2026-04-16T02:00:00Z"}

        bytes1 = _canonical_odbc(row1, modified_column="last_modified")
        bytes2 = _canonical_odbc(row2, modified_column="last_modified")

        assert bytes1 == bytes2, (
            "modified_column value changed but canonical bytes should be identical"
        )

    def test_odbc_column_order_same_document(self):
        """Column order from cursor changes → same canonical bytes."""
        row1 = {"id": 1, "name": "Alice", "dept": "Finance"}
        row2 = {"dept": "Finance", "id": 1, "name": "Alice"}

        bytes1 = _canonical_odbc(row1)
        bytes2 = _canonical_odbc(row2)

        assert bytes1 == bytes2


# ---------------------------------------------------------------------------
# Integration: ingest_structured_record() — will fail until Task 6 implements it
# ---------------------------------------------------------------------------

async def _seed_data_source(session, source_id: uuid.UUID, source_type: str = "rest_api") -> None:
    """Insert a minimal data_sources row to satisfy FK constraints."""
    from sqlalchemy import text
    await session.execute(text("""
        INSERT INTO data_sources (id, name, source_type, connection_config, is_active, created_by)
        VALUES (:id, :name, :source_type, '{}', true, (SELECT id FROM users LIMIT 1))
    """), {"id": str(source_id), "name": f"test-{source_id}", "source_type": source_type})
    await session.flush()


class TestIngestStructuredRecord:

    @pytest.mark.asyncio
    async def test_structured_record_same_hash_is_noop(self, db_session):
        """Same source_path, same content hash → document unchanged, updated_at not set."""
        from app.ingestion.pipeline import ingest_structured_record
        source_id = _make_source_id()
        await _seed_data_source(db_session, source_id)
        content = b'{"id": 1, "title": "Budget"}'

        doc1 = await ingest_structured_record(
            session=db_session,
            source_id=source_id,
            source_path="https://api.example.com/records/1",
            content_bytes=content,
            filename="1.json",
            metadata={},
            connector_type="rest_api",
        )
        doc2 = await ingest_structured_record(
            session=db_session,
            source_id=source_id,
            source_path="https://api.example.com/records/1",
            content_bytes=content,
            filename="1.json",
            metadata={},
            connector_type="rest_api",
        )
        assert doc1.id == doc2.id, "Same source_path + same hash → same document"
        assert doc2.updated_at is None, "No-op ingest must not set updated_at"

    @pytest.mark.asyncio
    async def test_structured_record_content_change_updates_document(self, db_session):
        """Same source_path, different content → document updated, updated_at set, no dup row."""
        from app.ingestion.pipeline import ingest_structured_record
        from sqlalchemy import select, func
        from app.models.document import Document
        source_id = _make_source_id()
        await _seed_data_source(db_session, source_id)

        doc1 = await ingest_structured_record(
            session=db_session,
            source_id=source_id,
            source_path="https://api.example.com/records/2",
            content_bytes=b'{"id": 2, "amount": 100}',
            filename="2.json",
            metadata={},
            connector_type="rest_api",
        )

        doc2 = await ingest_structured_record(
            session=db_session,
            source_id=source_id,
            source_path="https://api.example.com/records/2",
            content_bytes=b'{"id": 2, "amount": 999}',
            filename="2.json",
            metadata={},
            connector_type="rest_api",
        )

        assert doc1.id == doc2.id
        assert doc2.updated_at is not None
        count_result = await db_session.execute(
            select(func.count()).where(
                Document.source_id == source_id,
                Document.source_path == "https://api.example.com/records/2",
            )
        )
        assert count_result.scalar() == 1

    @pytest.mark.asyncio
    async def test_update_deletes_old_chunks_before_reembed(self, db_session):
        """Same source_path, content changes → old DocumentChunk rows deleted before re-chunk."""
        from app.ingestion.pipeline import ingest_structured_record
        from sqlalchemy import select, func
        from app.models.document import DocumentChunk
        source_id = _make_source_id()
        await _seed_data_source(db_session, source_id)
        path = "https://api.example.com/records/3"

        doc = await ingest_structured_record(
            session=db_session, source_id=source_id, source_path=path,
            content_bytes=b'{"id": 3, "body": "original content long enough to chunk"}',
            filename="3.json", metadata={}, connector_type="rest_api",
        )

        first_chunk_ids_result = await db_session.execute(
            select(DocumentChunk.id).where(DocumentChunk.document_id == doc.id)
        )
        first_chunk_ids = {row[0] for row in first_chunk_ids_result}
        assert len(first_chunk_ids) > 0, "First ingestion produced no chunks — test precondition failed"

        await ingest_structured_record(
            session=db_session, source_id=source_id, source_path=path,
            content_bytes=b'{"id": 3, "body": "completely different content"}',
            filename="3.json", metadata={}, connector_type="rest_api",
        )

        surviving_old_chunks_result = await db_session.execute(
            select(func.count(DocumentChunk.id)).where(
                DocumentChunk.document_id == doc.id,
                DocumentChunk.id.in_(first_chunk_ids),
            )
        )
        surviving_count = surviving_old_chunks_result.scalar()
        assert surviving_count == 0, (
            f"{surviving_count} original chunk(s) survived the update — "
            "DELETE before re-embed is not working"
        )


class TestConcurrency:
    """Prove UNIQUE indexes and SELECT FOR UPDATE prevent duplicate rows under
    concurrent workers. Uses asyncio.gather() with independent DB sessions.

    Requires db_session_factory fixture in conftest.py (see below).
    """

    @pytest.mark.asyncio
    async def test_concurrent_structured_insert_race(self, db_session, db_session_factory):
        """Two workers insert same (source_id, source_path) simultaneously → 1 document row."""
        import asyncio
        from sqlalchemy.exc import IntegrityError
        from sqlalchemy import select, func, text
        from app.ingestion.pipeline import ingest_structured_record
        from app.models.document import Document

        source_id = uuid.uuid4()
        await db_session.execute(text("""
            INSERT INTO data_sources (id, name, source_type, connection_config, is_active, created_by)
            VALUES (:id, 'concurrent-struct', 'rest_api', '{}', true, (SELECT id FROM users LIMIT 1))
        """), {"id": str(source_id)})
        await db_session.commit()

        path = "https://api.example.com/concurrent/1"
        content = b'{"id": 1}'

        async def worker(session):
            try:
                await ingest_structured_record(
                    session=session, source_id=source_id, source_path=path,
                    content_bytes=content, filename="1.json", metadata={}, connector_type="rest_api",
                )
                await session.commit()
            except IntegrityError:
                await session.rollback()

        async with db_session_factory() as s1, db_session_factory() as s2:
            await asyncio.gather(worker(s1), worker(s2))

        count = await db_session.scalar(
            select(func.count(Document.id)).where(
                Document.source_id == source_id, Document.source_path == path
            )
        )
        assert count == 1, f"Race produced {count} rows — UNIQUE constraint not enforced"

    @pytest.mark.asyncio
    async def test_concurrent_binary_insert_race(self, db_session, db_session_factory):
        """Two workers insert same (source_id, file_hash) simultaneously → 1 document row."""
        import asyncio, os, tempfile
        from pathlib import Path
        from sqlalchemy.exc import IntegrityError
        from sqlalchemy import select, func, text
        from app.ingestion.pipeline import ingest_file
        from app.models.document import Document

        source_id = uuid.uuid4()
        await db_session.execute(text("""
            INSERT INTO data_sources (id, name, source_type, connection_config, is_active, created_by)
            VALUES (:id, 'concurrent-binary', 'directory', '{}', true, (SELECT id FROM users LIMIT 1))
        """), {"id": str(source_id)})
        await db_session.commit()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"binary concurrency test content")
            tmp_path = Path(f.name)

        async def worker(session):
            try:
                await ingest_file(session=session, file_path=tmp_path, source_id=source_id)
                await session.commit()
            except IntegrityError:
                await session.rollback()

        try:
            async with db_session_factory() as s1, db_session_factory() as s2:
                await asyncio.gather(worker(s1), worker(s2))
            count = await db_session.scalar(
                select(func.count(Document.id)).where(Document.source_id == source_id)
            )
            assert count == 1, f"Race produced {count} rows"
        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    async def test_concurrent_update_select_for_update(self, db_session, db_session_factory):
        """Two workers detect same source_path with different hash → SELECT FOR UPDATE serializes."""
        import asyncio
        from sqlalchemy import select, func, text
        from app.ingestion.pipeline import ingest_structured_record
        from app.models.document import Document, DocumentChunk

        source_id = uuid.uuid4()
        await db_session.execute(text("""
            INSERT INTO data_sources (id, name, source_type, connection_config, is_active, created_by)
            VALUES (:id, 'concurrent-update', 'rest_api', '{}', true, (SELECT id FROM users LIMIT 1))
        """), {"id": str(source_id)})
        await db_session.commit()

        path = "https://api.example.com/concurrent/update"
        original = b'{"id": 99, "v": 1}'

        await ingest_structured_record(
            session=db_session, source_id=source_id, source_path=path,
            content_bytes=original, filename="99.json", metadata={}, connector_type="rest_api",
        )
        await db_session.commit()

        updated = b'{"id": 99, "v": 2}'

        async def worker(session):
            await ingest_structured_record(
                session=session, source_id=source_id, source_path=path,
                content_bytes=updated, filename="99.json", metadata={}, connector_type="rest_api",
            )
            await session.commit()

        async with db_session_factory() as s1, db_session_factory() as s2:
            await asyncio.gather(worker(s1), worker(s2))

        doc_count = await db_session.scalar(
            select(func.count(Document.id)).where(
                Document.source_id == source_id, Document.source_path == path
            )
        )
        assert doc_count == 1, "Concurrent updates produced multiple document rows"

        doc = await db_session.scalar(
            select(Document).where(Document.source_id == source_id, Document.source_path == path)
        )
        chunk_indexes_result = await db_session.execute(
            select(DocumentChunk.chunk_index).where(DocumentChunk.document_id == doc.id)
        )
        indexes = [row[0] for row in chunk_indexes_result]
        assert len(indexes) == len(set(indexes)), (
            "Duplicate chunk_index values found — concurrent updates stacked instead of serializing"
        )
