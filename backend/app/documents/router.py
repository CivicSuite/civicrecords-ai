import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.dependencies import require_department_scope, require_role
from app.database import get_async_session
from app.models.document import Document, DocumentChunk, IngestionStatus
from app.models.user import User, UserRole
from app.schemas.document import DocumentRead, DocumentChunkRead

router = APIRouter(prefix="/documents", tags=["documents"])


def _apply_department_filter(stmt, user: User):
    """Apply fail-closed department scope to a documents query.

    Admin users see every document. Non-admin users must have a department
    assignment; their query is filtered to their own department.
    """
    if user.role == UserRole.ADMIN:
        return stmt
    if user.department_id is None:
        raise HTTPException(
            status_code=403,
            detail="Access denied: user is not assigned to a department",
        )
    return stmt.where(Document.department_id == user.department_id)


@router.get("/", response_model=list[DocumentRead])
async def list_documents(source_id: uuid.UUID | None = None, status: IngestionStatus | None = None, limit: int = Query(default=50, le=500), offset: int = 0, session: AsyncSession = Depends(get_async_session), user: User = Depends(require_role(UserRole.STAFF))):
    stmt = select(Document).order_by(Document.ingested_at.desc().nulls_last())
    stmt = _apply_department_filter(stmt, user)
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
    require_department_scope(user, doc.department_id)
    return doc

@router.get("/{document_id}/chunks", response_model=list[DocumentChunkRead])
async def list_chunks(document_id: uuid.UUID, limit: int = Query(default=50, le=500), offset: int = 0, session: AsyncSession = Depends(get_async_session), user: User = Depends(require_role(UserRole.STAFF))):
    # Load the parent document so we can enforce department scope before
    # returning its chunks. 404 if document is missing; 403 if cross-department.
    doc = await session.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    require_department_scope(user, doc.department_id)
    result = await session.execute(select(DocumentChunk).where(DocumentChunk.document_id == document_id).order_by(DocumentChunk.chunk_index).offset(offset).limit(limit))
    return result.scalars().all()
