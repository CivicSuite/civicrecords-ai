from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.logger import verify_chain
from app.auth.dependencies import require_role
from app.database import get_async_session
from app.models.audit import AuditLog
from app.models.user import User, UserRole
from app.schemas.audit import AuditChainVerification, AuditLogQuery, AuditLogRead

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs", response_model=list[AuditLogRead])
async def list_audit_logs(
    query: AuditLogQuery = Depends(),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    stmt = select(AuditLog).order_by(AuditLog.id.desc())

    if query.action:
        stmt = stmt.where(AuditLog.action.contains(query.action))
    if query.resource_type:
        stmt = stmt.where(AuditLog.resource_type == query.resource_type)
    if query.user_id:
        stmt = stmt.where(AuditLog.user_id == query.user_id)
    if query.start_date:
        stmt = stmt.where(AuditLog.timestamp >= query.start_date)
    if query.end_date:
        stmt = stmt.where(AuditLog.timestamp <= query.end_date)

    stmt = stmt.offset(query.offset).limit(query.limit)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/verify", response_model=AuditChainVerification)
async def verify_audit_chain(
    limit: int = 1000,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    is_valid, count, error = await verify_chain(session, limit)
    return AuditChainVerification(
        is_valid=is_valid, entries_checked=count, error_message=error
    )


@router.get("/export")
async def export_audit_logs(
    format: str = "json",
    start_date: str | None = None,
    end_date: str | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    from datetime import datetime
    from fastapi.responses import StreamingResponse
    import csv
    import io
    import json

    stmt = select(AuditLog).order_by(AuditLog.id.asc())
    if start_date:
        stmt = stmt.where(AuditLog.timestamp >= datetime.fromisoformat(start_date))
    if end_date:
        stmt = stmt.where(AuditLog.timestamp <= datetime.fromisoformat(end_date))

    result = await session.execute(stmt)
    logs = result.scalars().all()

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "id", "prev_hash", "entry_hash", "timestamp", "user_id",
            "action", "resource_type", "resource_id", "details", "ai_generated",
        ])
        for log in logs:
            writer.writerow([
                log.id, log.prev_hash, log.entry_hash, log.timestamp.isoformat(),
                str(log.user_id) if log.user_id else "", log.action, log.resource_type,
                log.resource_id or "", json.dumps(log.details) if log.details else "",
                log.ai_generated,
            ])
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=audit_log.csv"},
        )
    else:
        data = [
            {
                "id": log.id,
                "prev_hash": log.prev_hash,
                "entry_hash": log.entry_hash,
                "timestamp": log.timestamp.isoformat(),
                "user_id": str(log.user_id) if log.user_id else None,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "details": log.details,
                "ai_generated": log.ai_generated,
            }
            for log in logs
        ]
        return StreamingResponse(
            iter([json.dumps(data, indent=2)]),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=audit_log.json"},
        )
