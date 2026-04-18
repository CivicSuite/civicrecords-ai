# backend/app/datasources/sync_failures_router.py
"""API endpoints for sync failure management (P7)."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_async_session
from app.models.document import DataSource
from app.models.sync_failure import SyncFailure, SyncRunLog
from app.models.user import User, UserRole
from app.schemas.sync_failure import SyncFailureRead, SyncRunLogRead

router = APIRouter(prefix="/datasources", tags=["sync-failures"])


def _require_admin():
    return Depends(require_role(UserRole.ADMIN))


@router.get("/{source_id}/sync-failures", response_model=list[SyncFailureRead])
async def list_sync_failures(
    source_id: uuid.UUID,
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    query = select(SyncFailure).where(SyncFailure.source_id == source_id)
    if status:
        query = query.where(SyncFailure.status == status)
    query = query.order_by(SyncFailure.first_failed_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/{source_id}/sync-failures/{failure_id}/retry")
async def retry_sync_failure(
    source_id: uuid.UUID,
    failure_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    failure = await db.get(SyncFailure, failure_id)
    if not failure or failure.source_id != source_id:
        raise HTTPException(status_code=404, detail="Sync failure not found")
    failure.status = "retrying"
    failure.dismissed_at = None
    await db.commit()
    return {"status": "ok"}


@router.post("/{source_id}/sync-failures/{failure_id}/dismiss")
async def dismiss_sync_failure(
    source_id: uuid.UUID,
    failure_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    failure = await db.get(SyncFailure, failure_id)
    if not failure or failure.source_id != source_id:
        raise HTTPException(status_code=404, detail="Sync failure not found")
    failure.status = "dismissed"
    failure.dismissed_at = datetime.now(timezone.utc)
    failure.dismissed_by = current_user.id
    await db.commit()
    return {"status": "ok"}


@router.post("/{source_id}/sync-failures/retry-all")
async def retry_all_sync_failures(
    source_id: uuid.UUID,
    status: str = Query(..., description="Status to reset — required"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    result = await db.execute(
        select(SyncFailure).where(
            SyncFailure.source_id == source_id,
            SyncFailure.status == status,
        )
    )
    rows = result.scalars().all()
    for row in rows:
        row.status = "retrying"
        row.dismissed_at = None
    await db.commit()
    return {"updated": len(rows)}


@router.post("/{source_id}/sync-failures/dismiss-all")
async def dismiss_all_sync_failures(
    source_id: uuid.UUID,
    status: str = Query(..., description="Status to dismiss — required"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    result = await db.execute(
        select(SyncFailure).where(
            SyncFailure.source_id == source_id,
            SyncFailure.status == status,
        )
    )
    rows = result.scalars().all()
    now = datetime.now(timezone.utc)
    for row in rows:
        row.status = "dismissed"
        row.dismissed_at = now
        row.dismissed_by = current_user.id
    await db.commit()
    return {"updated": len(rows)}


@router.post("/{source_id}/unpause")
async def unpause_source(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    source = await db.get(DataSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")
    source.sync_paused = False
    source.sync_paused_at = None
    source.sync_paused_reason = "grace_period"  # triggers threshold=2 on next sync run
    source.consecutive_failure_count = 0
    await db.commit()
    return {"status": "ok", "grace_period": True}


@router.get("/{source_id}/sync-run-log", response_model=list[SyncRunLogRead])
async def get_sync_run_log(
    source_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    result = await db.execute(
        select(SyncRunLog)
        .where(SyncRunLog.source_id == source_id)
        .order_by(SyncRunLog.started_at.desc())
        .limit(limit)
    )
    return result.scalars().all()
