import asyncio
import uuid
from pathlib import Path

from app.worker import celery_app
from app.database import async_session_maker
from app.ingestion.pipeline import ingest_file, ingest_directory
from app.audit.logger import write_audit_log


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="civicrecords.ingest_file", bind=True, max_retries=2)
def task_ingest_file(self, file_path: str, source_id: str, chunk_size: int = 500, chunk_overlap: int = 50, embed_model: str = "nomic-embed-text", user_id: str | None = None):
    async def _ingest():
        async with async_session_maker() as session:
            doc = await ingest_file(session=session, file_path=Path(file_path), source_id=uuid.UUID(source_id), chunk_size=chunk_size, chunk_overlap=chunk_overlap, embed_model=embed_model)
            await write_audit_log(session=session, action="ingest_file", resource_type="document", resource_id=str(doc.id), user_id=uuid.UUID(user_id) if user_id else None, details={"filename": doc.filename, "status": doc.ingestion_status.value, "chunks": doc.chunk_count})
            return {"document_id": str(doc.id), "status": doc.ingestion_status.value}
    try:
        return _run_async(_ingest())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(name="civicrecords.ingest_source", bind=True)
def task_ingest_source(self, source_id: str, user_id: str | None = None):
    async def _ingest():
        async with async_session_maker() as session:
            from sqlalchemy import select
            from app.models.document import DataSource
            from datetime import datetime, timezone
            source = await session.get(DataSource, uuid.UUID(source_id))
            if not source:
                return {"error": "Source not found"}
            config = source.connection_config
            directory = Path(config.get("path", ""))
            if not directory.is_dir():
                return {"error": f"Directory not found: {directory}"}
            stats = await ingest_directory(session=session, directory=directory, source_id=source.id)
            source.last_ingestion_at = datetime.now(timezone.utc)
            await session.commit()
            await write_audit_log(session=session, action="ingest_source", resource_type="data_source", resource_id=source_id, user_id=uuid.UUID(user_id) if user_id else None, details=stats)
            return stats
    return _run_async(_ingest())
