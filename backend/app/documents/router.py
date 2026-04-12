import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.dependencies import require_role
from app.database import get_async_session
from app.models.document import Document, DocumentChunk, IngestionStatus
from app.models.user import User, UserRole
from app.schemas.document import DocumentRead, DocumentChunkRead

router = APIRouter(prefix="/documents", tags=["documents"])

@router.get("/", response_model=list[DocumentRead])
async def list_documents(source_id: uuid.UUID | None = None, status: IngestionStatus | None = None, limit: int = Query(default=50, le=500), offset: int = 0, session: AsyncSession = Depends(get_async_session), user: User = Depends(require_role(UserRole.STAFF))):
    stmt = select(Document).order_by(Document.ingested_at.desc().nulls_last())
    if source_id:
        stmt = stmt.where(Document.source_id == source_id)
    if status:
        stmt = stmt.where(Document.ingestion_status == status)
    stmt = stmt.offset(offset).limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()

@router.get("/{document_id}", response_model=DocumentRead)
async def get_document(document_id: uuid.UUID, session: AsyncSession = Depends(get_async_session), user: User = Depends(require_role(UserRole.STAFF))):
    doc = await session.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc

@router.get("/{document_id}/chunks", response_model=list[DocumentChunkRead])
async def list_chunks(document_id: uuid.UUID, limit: int = Query(default=50, le=500), offset: int = 0, session: AsyncSession = Depends(get_async_session), user: User = Depends(require_role(UserRole.STAFF))):
    result = await session.execute(select(DocumentChunk).where(DocumentChunk.document_id == document_id).order_by(DocumentChunk.chunk_index).offset(offset).limit(limit))
    return result.scalars().all()
