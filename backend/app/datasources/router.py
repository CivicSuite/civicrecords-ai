import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.audit.logger import write_audit_log
from app.auth.dependencies import require_role
from app.database import get_async_session
from app.models.document import DataSource, Document, DocumentChunk, IngestionStatus, SourceType
from app.models.user import User, UserRole
from app.schemas.document import DataSourceCreate, DataSourceRead, DataSourceUpdate, IngestionStats

router = APIRouter(prefix="/datasources", tags=["datasources"])

@router.post("/", response_model=DataSourceRead, status_code=201)
async def create_datasource(data: DataSourceCreate, session: AsyncSession = Depends(get_async_session), user: User = Depends(require_role(UserRole.ADMIN))):
    existing = await session.execute(select(DataSource).where(DataSource.name == data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Name already taken")
    source = DataSource(name=data.name, source_type=data.source_type, connection_config=data.connection_config, schedule_minutes=data.schedule_minutes, created_by=user.id)
    session.add(source)
    await session.commit()
    await session.refresh(source)
    await write_audit_log(session=session, action="create_datasource", resource_type="data_source", resource_id=str(source.id), user_id=user.id, details={"name": data.name, "type": data.source_type.value})
    return source

@router.get("/", response_model=list[DataSourceRead])
async def list_datasources(session: AsyncSession = Depends(get_async_session), user: User = Depends(require_role(UserRole.STAFF))):
    result = await session.execute(select(DataSource).order_by(DataSource.created_at.desc()))
    return result.scalars().all()

@router.patch("/{source_id}", response_model=DataSourceRead)
async def update_datasource(source_id: uuid.UUID, data: DataSourceUpdate, session: AsyncSession = Depends(get_async_session), user: User = Depends(require_role(UserRole.ADMIN))):
    source = await session.get(DataSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")
    if data.name is not None:
        source.name = data.name
    if data.connection_config is not None:
        source.connection_config = data.connection_config
    if data.schedule_minutes is not None:
        source.schedule_minutes = data.schedule_minutes
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
    from pathlib import Path
    with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    result = await session.execute(select(DataSource).where(DataSource.name == "_uploads", DataSource.source_type == SourceType.UPLOAD))
    upload_source = result.scalar_one_or_none()
    if not upload_source:
        upload_source = DataSource(name="_uploads", source_type=SourceType.UPLOAD, created_by=user.id)
        session.add(upload_source)
        await session.flush()
    from app.ingestion.tasks import task_ingest_file
    task = task_ingest_file.delay(file_path=tmp_path, source_id=str(upload_source.id), user_id=str(user.id))
    return {"task_id": task.id, "filename": file.filename, "status": "queued"}

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
