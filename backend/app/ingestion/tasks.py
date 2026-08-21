import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from civiccore.ingest import ingest_bytes, ingest_directory, ingest_file

from app.worker import celery_app
from app.audit.logger import write_audit_log
from app.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def worker_session_scope():
    # scheduler.py:30 pattern — engine must be built inside the running loop
    # because asyncpg connections bind their _loop/_waiter to the loop that
    # first awaits I/O on them; reusing the engine across _run_async's
    # per-task loops raises "Event loop is closed" on the second task.
    engine = create_async_engine(
        settings.database_url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with maker() as session:
            yield session
    finally:
        await engine.dispose()


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="civicrecords.ingest_file", bind=True, max_retries=2)
def task_ingest_file(
    self,
    file_path: str,
    source_id: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    embed_model: str = "nomic-embed-text",
    user_id: str | None = None,
):
    async def _ingest():
        async with worker_session_scope() as session:
            doc = await ingest_file(
                session=session,
                file_path=Path(file_path),
                source_id=uuid.UUID(source_id),
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                embed_model=embed_model,
            )
            await write_audit_log(
                session=session,
                action="ingest_file",
                resource_type="document",
                resource_id=str(doc.id),
                user_id=uuid.UUID(user_id) if user_id else None,
                details={
                    "filename": doc.filename,
                    "status": doc.ingestion_status.value,
                    "chunks": doc.chunk_count,
                },
            )
            return {"document_id": str(doc.id), "status": doc.ingestion_status.value}

    try:
        return _run_async(_ingest())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(name="civicrecords.ingest_source", bind=True, soft_time_limit=3600, time_limit=4200)
def task_ingest_source(self, source_id: str, user_id: str | None = None):
    async def _ingest():
        async with worker_session_scope() as session:
            from app.models.document import DataSource
            from datetime import datetime, timezone

            source = await session.get(DataSource, uuid.UUID(source_id))
            if not source:
                return {"error": "Source not found"}

            config = source.connection_config
            source_type = source.source_type.value if hasattr(source.source_type, 'value') else str(source.source_type)

            # Dispatch by source type
            if source_type == "manual_drop":
                return await _ingest_manual_drop_source(session, source, user_id)

            # Connector types with per-record failure tracking
            if source_type in ("rest_api", "odbc"):
                from app.connectors import get_connector
                from app.ingestion.sync_runner import run_connector_sync_with_retry
                connector = get_connector(source_type, config)
                authenticated = await connector.authenticate()
                if not authenticated:
                    return {"error": f"{source_type} authentication failed"}
                try:
                    return await run_connector_sync_with_retry(
                        connector=connector,
                        source_id=source_id,
                        session=session,
                    )
                except (IOError, OSError) as exc:
                    # Task-level retry fires only for transient whole-run failures.
                    # Per-record errors are absorbed into sync_failures inside the runner.
                    raise self.retry(exc=exc, countdown=30)

            if source_type == "file_system":
                directory = Path(config.get("path", ""))
                if not directory.is_dir():
                    return {"error": f"Directory not found: {directory}"}

                stats = await ingest_directory(
                    session=session,
                    directory=directory,
                    source_id=source.id,
                )
                source.last_ingestion_at = datetime.now(timezone.utc)
                await session.commit()

                await write_audit_log(
                    session=session,
                    action="ingest_source",
                    resource_type="data_source",
                    resource_id=source_id,
                    user_id=uuid.UUID(user_id) if user_id else None,
                    details=stats,
                )
                return stats

            return {"error": f"Unsupported source type: {source_type!r}"}

    return _run_async(_ingest())


async def _ingest_manual_drop_source(session, source, user_id: str | None) -> dict:
    """Ingest documents from a watched drop folder via the ManualDropConnector."""
    from app.connectors import manual_drop as _drop_mod

    connector = _drop_mod.ManualDropConnector(source.connection_config)

    authenticated = await connector.authenticate()
    if not authenticated:
        return {"error": "ManualDrop: drop folder not accessible"}

    discovered = await connector.discover()

    ingested = 0
    errors = 0

    try:
        for record in discovered:
            try:
                fetched = await connector.fetch(record.source_path)

                doc = await ingest_file_from_bytes(
                    session=session,
                    content=fetched.content,
                    filename=fetched.filename,
                    file_type=fetched.file_type,
                    source_id=source.id,
                    source_path=fetched.source_path,
                    metadata=fetched.metadata,
                )
                if doc:
                    ingested += 1
                    # Archive the processed file
                    connector.archive_file(record.source_path)

            except Exception as exc:
                logger.error(
                    "Fetch failed",
                    extra={
                        "error_class": type(exc).__name__,
                        "record_id": record.source_path,
                        "status_code": getattr(exc, "status_code", None),
                        "retry_count": getattr(exc, "retry_count", 0),
                    },
                )
                errors += 1

        # Cursor-on-success: only write after all fetches complete without unhandled error
        source.last_ingestion_at = datetime.now(timezone.utc)
        source.last_sync_at = datetime.now(timezone.utc)
        source.last_sync_cursor = str(datetime.now(timezone.utc))
        await session.commit()

    finally:
        connector.close()

    stats = {"ingested": ingested, "errors": errors, "discovered": len(discovered)}

    await write_audit_log(
        session=session,
        action="ingest_manual_drop_source",
        resource_type="data_source",
        resource_id=str(source.id),
        user_id=uuid.UUID(user_id) if user_id else None,
        details=stats,
    )

    logger.info("ManualDrop ingestion complete for source %s: %s", source.id, stats)
    return stats


async def ingest_file_from_bytes(
    session,
    content: bytes,
    filename: str,
    file_type: str,
    source_id: uuid.UUID,
    source_path: str | None = None,
    metadata: dict | None = None,
) -> object | None:
    """Ingest a document from raw bytes through the CivicCore pipeline."""
    import logging

    logger = logging.getLogger(__name__)

    try:
        return await ingest_bytes(
            session=session,
            content=content,
            filename=filename,
            source_id=source_id,
            source_path=source_path or filename,
            metadata=metadata,
        )
    except Exception as exc:
        logger.error("Failed to ingest %s: %s", filename, exc)
        return None
