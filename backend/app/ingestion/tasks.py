import asyncio
import uuid
from pathlib import Path

from celery.signals import worker_process_init
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.worker import celery_app
from app.ingestion.pipeline import ingest_file, ingest_directory
from app.audit.logger import write_audit_log
from app.config import settings

_engine = None
_session_maker = None


@worker_process_init.connect
def init_worker_db(**kwargs):
    global _engine, _session_maker
    _engine = create_async_engine(
        settings.database_url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    _session_maker = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


def get_worker_session():
    if _session_maker is None:
        # Fallback for non-worker contexts (tests, CLI)
        from app.database import async_session_maker
        return async_session_maker()
    return _session_maker()


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
        async with get_worker_session() as session:
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


@celery_app.task(name="civicrecords.ingest_source", bind=True)
def task_ingest_source(self, source_id: str, user_id: str | None = None):
    async def _ingest():
        async with get_worker_session() as session:
            from app.models.document import DataSource
            from datetime import datetime, timezone

            source = await session.get(DataSource, uuid.UUID(source_id))
            if not source:
                return {"error": "Source not found"}

            config = source.connection_config
            source_type = source.source_type.value if hasattr(source.source_type, 'value') else str(source.source_type)

            # Dispatch by source type
            if source_type == "email":
                return await _ingest_email_source(session, source, user_id)
            if source_type == "manual_drop":
                return await _ingest_manual_drop_source(session, source, user_id)

            # Default: directory-based ingestion
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

    return _run_async(_ingest())


async def _ingest_email_source(session, source, user_id: str | None) -> dict:
    """Ingest documents from an IMAP email source via the connector protocol."""
    import logging
    from datetime import datetime, timezone
    from app.connectors import imap_email as _imap_mod

    logger = logging.getLogger(__name__)

    connector = _imap_mod.ImapEmailConnector(source.connection_config)

    authenticated = await connector.authenticate()
    if not authenticated:
        return {"error": "IMAP authentication failed"}

    discovered = await connector.discover()

    ingested = 0
    skipped = 0
    errors = 0

    for record in discovered:
        try:
            fetched = await connector.fetch(record.source_path)

            # Extract safe attachments
            safe_attachments = connector.extract_safe_attachments(fetched.content)

            # Also ingest the email body itself as a document
            email_doc = await ingest_file_from_bytes(
                session=session,
                content=fetched.content,
                filename=fetched.filename,
                file_type="eml",
                source_id=source.id,
            )
            if email_doc:
                ingested += 1

            # Ingest each safe attachment
            for attachment in safe_attachments:
                att_doc = await ingest_file_from_bytes(
                    session=session,
                    content=attachment.content,
                    filename=attachment.filename,
                    file_type=attachment.file_type,
                    source_id=source.id,
                )
                if att_doc:
                    ingested += 1

        except Exception as exc:
            logger.error("Failed to ingest email %s: %s", record.source_path, exc)
            errors += 1

    source.last_ingestion_at = datetime.now(timezone.utc)
    await session.commit()

    stats = {"ingested": ingested, "skipped": skipped, "errors": errors, "discovered": len(discovered)}

    await write_audit_log(
        session=session,
        action="ingest_email_source",
        resource_type="data_source",
        resource_id=str(source.id),
        user_id=uuid.UUID(user_id) if user_id else None,
        details=stats,
    )

    logger.info("Email ingestion complete for source %s: %s", source.id, stats)
    return stats


async def _ingest_manual_drop_source(session, source, user_id: str | None) -> dict:
    """Ingest documents from a watched drop folder via the ManualDropConnector."""
    import logging
    from datetime import datetime, timezone
    from app.connectors import manual_drop as _drop_mod

    logger = logging.getLogger(__name__)

    connector = _drop_mod.ManualDropConnector(source.connection_config)

    authenticated = await connector.authenticate()
    if not authenticated:
        return {"error": "ManualDrop: drop folder not accessible"}

    discovered = await connector.discover()

    ingested = 0
    errors = 0

    for record in discovered:
        try:
            fetched = await connector.fetch(record.source_path)

            doc = await ingest_file_from_bytes(
                session=session,
                content=fetched.content,
                filename=fetched.filename,
                file_type=fetched.file_type,
                source_id=source.id,
            )
            if doc:
                ingested += 1
                # Archive the processed file
                connector.archive_file(record.source_path)

        except Exception as exc:
            logger.error("Failed to ingest drop file %s: %s", record.source_path, exc)
            errors += 1

    source.last_ingestion_at = datetime.now(timezone.utc)
    await session.commit()

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
) -> object | None:
    """Ingest a document from raw bytes (used for email attachments).

    Writes content to a temp file and delegates to ingest_file().
    Returns the Document object or None on failure.
    """
    import tempfile
    import logging

    logger = logging.getLogger(__name__)

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_type}") as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)

        doc = await ingest_file(
            session=session,
            file_path=tmp_path,
            source_id=source_id,
        )
        return doc
    except Exception as exc:
        logger.error("Failed to ingest %s: %s", filename, exc)
        return None
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
