import asyncio
import hashlib
import logging
import re as _re
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.logger import write_audit_log
from app.auth.dependencies import require_role
from app.database import get_async_session
from app.models.document import DataSource, Document, DocumentChunk, IngestionStatus, SourceType
from app.models.user import User, UserRole
from app.schemas.document import DataSourceAdminRead, DataSourceCreate, DataSourceRead, DataSourceUpdate, IngestionStats

async def _double_fetch_hashes(
    connector, first_source_path: str, data_key: str | None
) -> tuple[str, str, list[str]]:
    """Fetch a record twice (500ms apart) and compare canonical hashes.

    Returns (hash1, hash2, differing_top_level_keys).
    Used to detect non-deterministic envelopes at test-connection time.
    """
    import json
    from app.connectors.rest_api import _extract_dotted

    async def _fetch_and_hash():
        fetched = await connector.fetch(first_source_path)
        parsed = json.loads(fetched.content.decode("utf-8"))
        record = _extract_dotted(parsed, data_key)
        canonical = json.dumps(record, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest(), parsed

    hash1, parsed1 = await _fetch_and_hash()
    await asyncio.sleep(0.5)
    hash2, parsed2 = await _fetch_and_hash()

    differing_keys: list[str] = []
    if hash1 != hash2 and isinstance(parsed1, dict) and isinstance(parsed2, dict):
        differing_keys = [
            k for k in set(parsed1) | set(parsed2)
            if parsed1.get(k) != parsed2.get(k)
        ]

    return hash1, hash2, differing_keys


_CRED_SCRUB = _re.compile(
    r"(api_key|token|client_secret|password|connection_string)\s*=\s*\S+",
    _re.IGNORECASE,
)


def _scrub_error(msg: str) -> str:
    """Remove credential values from error message strings."""
    return _CRED_SCRUB.sub(r"\1=[REDACTED]", msg)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/datasources", tags=["datasources"])

@router.post("/", response_model=DataSourceAdminRead, status_code=201)
async def create_datasource(data: DataSourceCreate, session: AsyncSession = Depends(get_async_session), user: User = Depends(require_role(UserRole.ADMIN))):
    existing = await session.execute(select(DataSource).where(DataSource.name == data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Name already taken")
    source = DataSource(
        name=data.name,
        source_type=data.source_type,
        connection_config=data.connection_config,
        sync_schedule=data.sync_schedule,
        schedule_enabled=data.schedule_enabled,
        created_by=user.id,
    )
    session.add(source)
    await session.commit()
    await session.refresh(source)
    await write_audit_log(session=session, action="create_datasource", resource_type="data_source", resource_id=str(source.id), user_id=user.id, details={"name": data.name, "type": data.source_type.value})
    return source

@router.get("/", response_model=list[DataSourceRead])
async def list_datasources(session: AsyncSession = Depends(get_async_session), user: User = Depends(require_role(UserRole.STAFF))):
    from app.ingestion.cron_utils import compute_next_sync_at
    from app.models.sync_failure import SyncFailure

    result = await session.execute(select(DataSource).order_by(DataSource.created_at.desc()))
    sources = result.scalars().all()

    # One aggregated query for active failure counts — no N+1
    failure_counts_result = await session.execute(
        select(SyncFailure.source_id, func.count(SyncFailure.id).label("count"))
        .where(SyncFailure.status.in_(["retrying", "permanently_failed"]))
        .group_by(SyncFailure.source_id)
    )
    failure_counts: dict[str, int] = {
        str(row.source_id): row.count for row in failure_counts_result
    }

    output = []
    for source in sources:
        data = DataSourceRead.model_validate(source)
        active_failures = failure_counts.get(str(source.id), 0)
        data.active_failure_count = active_failures

        if source.sync_paused:
            data.health_status = "circuit_open"
        elif source.consecutive_failure_count > 0 or active_failures > 0:
            data.health_status = "degraded"
        else:
            data.health_status = "healthy"

        if source.sync_schedule and source.schedule_enabled and not source.sync_paused:
            data.next_sync_at = compute_next_sync_at(source.sync_schedule, source.last_sync_at)
        output.append(data)
    return output

@router.patch("/{source_id}", response_model=DataSourceAdminRead)
async def update_datasource(source_id: uuid.UUID, data: DataSourceUpdate, session: AsyncSession = Depends(get_async_session), user: User = Depends(require_role(UserRole.ADMIN))):
    source = await session.get(DataSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")
    if data.name is not None:
        source.name = data.name
    if data.connection_config is not None:
        source.connection_config = data.connection_config
    if data.sync_schedule is not None:
        source.sync_schedule = data.sync_schedule
    if data.schedule_enabled is not None:
        source.schedule_enabled = data.schedule_enabled
    if data.is_active is not None:
        source.is_active = data.is_active
    await session.commit()
    await session.refresh(source)
    return source

@router.post("/{source_id}/ingest")
async def trigger_ingestion(source_id: uuid.UUID, session: AsyncSession = Depends(get_async_session), user: User = Depends(require_role(UserRole.STAFF))):
    source = await session.get(DataSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")
    from app.ingestion.tasks import task_ingest_source
    task = task_ingest_source.delay(source_id=str(source_id), user_id=str(user.id))
    return {"task_id": task.id, "status": "queued"}

@router.post("/upload")
async def upload_file(file: UploadFile = File(...), session: AsyncSession = Depends(get_async_session), user: User = Depends(require_role(UserRole.STAFF))):
    import tempfile
    from pathlib import Path, PurePosixPath
    upload_dir = Path("/tmp/civicrecords-uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    import uuid as _uuid
    # Sanitize filename to prevent path traversal attacks
    raw_name = file.filename or "upload"
    safe_name = PurePosixPath(raw_name).name or "upload"
    dest = upload_dir / f"{_uuid.uuid4().hex}_{safe_name}"
    import aiofiles
    MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB
    total = 0
    too_large = False
    async with aiofiles.open(dest, "wb") as f:
        while chunk := await file.read(8192):
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                too_large = True
                break
            await f.write(chunk)
    if too_large:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=413, detail="File too large (max 100 MB)")
    tmp_path = str(dest)
    result = await session.execute(select(DataSource).where(DataSource.name == "_uploads", DataSource.source_type == SourceType.UPLOAD))
    upload_source = result.scalar_one_or_none()
    if not upload_source:
        upload_source = DataSource(name="_uploads", source_type=SourceType.UPLOAD, created_by=user.id)
        session.add(upload_source)
        await session.commit()
        await session.refresh(upload_source)
    from app.ingestion.tasks import task_ingest_file
    task = task_ingest_file.delay(file_path=tmp_path, source_id=str(upload_source.id), user_id=str(user.id))
    return {"task_id": task.id, "filename": file.filename, "status": "queued"}

@router.post("/documents/{document_id}/re-ingest")
async def re_ingest_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    """Re-ingest a failed document. Resets status to pending and queues for processing."""
    doc = await session.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.ingestion_status != IngestionStatus.FAILED:
        raise HTTPException(
            status_code=400,
            detail=f"Can only re-ingest failed documents (current: {doc.ingestion_status.value})",
        )

    doc.ingestion_status = IngestionStatus.PENDING
    doc.ingestion_error = None
    await session.commit()

    from app.ingestion.tasks import task_ingest_file
    task = task_ingest_file.delay(
        file_path=doc.source_path,
        source_id=str(doc.source_id),
        user_id=str(user.id),
    )

    await write_audit_log(
        session=session, action="re_ingest_document", resource_type="document",
        resource_id=str(document_id), user_id=user.id,
    )

    return {"task_id": task.id, "document_id": str(document_id), "status": "queued"}


@router.get("/stats", response_model=IngestionStats)
async def ingestion_stats(session: AsyncSession = Depends(get_async_session), user: User = Depends(require_role(UserRole.STAFF))):
    total_sources = (await session.execute(select(func.count(DataSource.id)))).scalar() or 0
    active_sources = (await session.execute(select(func.count(DataSource.id)).where(DataSource.is_active.is_(True)))).scalar() or 0
    total_documents = (await session.execute(select(func.count(Document.id)))).scalar() or 0
    total_chunks = (await session.execute(select(func.count(DocumentChunk.id)))).scalar() or 0
    status_counts = {}
    for status in IngestionStatus:
        count = (await session.execute(select(func.count(Document.id)).where(Document.ingestion_status == status))).scalar() or 0
        status_counts[status.value] = count
    return IngestionStats(total_sources=total_sources, active_sources=active_sources, total_documents=total_documents, documents_by_status=status_counts, total_chunks=total_chunks)


# --- Test connection (does NOT persist or log credentials) ---

class TestConnectionRequest(BaseModel):
    """Dedicated schema for test-connection. NOT the create schema.

    Security: credentials in this request body are never persisted, never
    written to audit logs, and never returned in the response.
    """
    source_type: str  # imap/file_share/manual_drop/rest_api/odbc
    host: str | None = None
    port: int | None = None
    path: str | None = None
    username: str | None = None
    password: str | None = None
    # Connector configs for rest_api and odbc
    rest_api_config: dict[str, Any] | None = None
    odbc_config: dict[str, Any] | None = None


class TestConnectionResponse(BaseModel):
    success: bool
    message: str
    latency_ms: int | None = None
    status: str | None = None
    warning: str | None = None
    differing_keys: list[str] | None = None


@router.post("/test-connection", response_model=TestConnectionResponse)
async def test_connection(
    body: TestConnectionRequest,
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Test connectivity to a data source without persisting anything.

    This endpoint validates the connection parameters and attempts a test
    connection. Credentials are NOT persisted, NOT logged, and NOT returned.
    """
    if body.source_type == "imap":
        if not body.host or not body.username:
            return TestConnectionResponse(success=False, message="IMAP requires host and username")
        try:
            import imaplib
            port = body.port or 993
            conn = imaplib.IMAP4_SSL(body.host, port)
            if body.username and body.password:
                conn.login(body.username, body.password)
            conn.logout()
            return TestConnectionResponse(success=True, message=f"Connected to {body.host}:{port}")
        except Exception as e:
            # Never expose credentials in error messages
            error_msg = str(e)
            if body.password and body.password in error_msg:
                error_msg = "Authentication failed"
            return TestConnectionResponse(success=False, message=f"IMAP connection failed: {error_msg}")

    elif body.source_type == "file_share":
        if not body.path:
            return TestConnectionResponse(success=False, message="File share requires a path")
        target = Path(body.path)
        if target.exists() and target.is_dir():
            file_count = len(list(target.iterdir()))
            return TestConnectionResponse(success=True, message=f"Path accessible: {file_count} items found")
        return TestConnectionResponse(success=False, message=f"Path not accessible or not a directory")

    elif body.source_type == "manual_drop":
        if not body.path:
            return TestConnectionResponse(success=False, message="Manual drop requires a path")
        target = Path(body.path)
        if target.exists() and target.is_dir():
            return TestConnectionResponse(success=True, message="Drop folder accessible")
        return TestConnectionResponse(success=False, message="Drop folder not accessible")

    elif body.source_type in ("rest_api", "odbc"):
        config_dict = body.rest_api_config if body.source_type == "rest_api" else body.odbc_config
        if not config_dict:
            return TestConnectionResponse(
                success=False,
                message=f"{body.source_type} requires a config object in "
                        f"{'rest_api_config' if body.source_type == 'rest_api' else 'odbc_config'}",
            )
        from app.connectors import get_connector
        connector = None
        try:
            connector = get_connector(body.source_type, config_dict)
            t0 = time.monotonic()
            async with asyncio.timeout(10):
                await connector.authenticate()
                result = await connector.health_check()
            latency_ms = int((time.monotonic() - t0) * 1000)
            if result.status.value == "healthy":
                # Pollution detection: only for REST API with discovered records
                warning = None
                differing_keys = None
                if body.source_type == "rest_api":
                    try:
                        discovered = await connector.discover()
                        if discovered:
                            first_path = discovered[0].source_path
                            data_key = config_dict.get("data_key")
                            h1, h2, diff_keys = await _double_fetch_hashes(
                                connector, first_path, data_key
                            )
                            if h1 != h2:
                                warning = "non_deterministic_response"
                                differing_keys = diff_keys
                    except Exception as poll_exc:
                        logger.debug("Pollution detection skipped: %s", poll_exc)

                return TestConnectionResponse(
                    success=True,
                    message="Connection successful",
                    latency_ms=result.latency_ms if result.latency_ms is not None else latency_ms,
                    status="healthy",
                    warning=warning,
                    differing_keys=differing_keys,
                )
            else:
                err = _scrub_error(result.error_message or result.status.value)
                return TestConnectionResponse(success=False, message=f"Connection unhealthy: {err}")
        except TimeoutError:
            return TestConnectionResponse(
                success=False, message="Connection timed out after 10 seconds"
            )
        except Exception as exc:
            return TestConnectionResponse(
                success=False, message=_scrub_error(str(exc))
            )
        finally:
            if connector is not None:
                connector.close()

    return TestConnectionResponse(success=False, message=f"Unknown source type: {body.source_type}")
