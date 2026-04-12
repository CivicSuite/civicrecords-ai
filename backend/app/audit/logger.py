import hashlib
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


def _compute_hash(prev_hash: str, timestamp: str, user_id: str, action: str, details: str) -> str:
    payload = f"{prev_hash}|{timestamp}|{user_id}|{action}|{details}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def get_last_hash(session: AsyncSession) -> str:
    result = await session.execute(
        select(AuditLog.entry_hash).order_by(AuditLog.id.desc()).limit(1)
    )
    last = result.scalar_one_or_none()
    return last if last else "0" * 64


async def write_audit_log(
    session: AsyncSession,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    user_id: uuid.UUID | None = None,
    details: dict | None = None,
    ai_generated: bool = False,
) -> AuditLog:
    prev_hash = await get_last_hash(session)
    now = datetime.now(timezone.utc)
    timestamp_str = now.isoformat()
    user_str = str(user_id) if user_id else "system"
    details_str = json.dumps(details, sort_keys=True, default=str) if details else ""

    entry_hash = _compute_hash(prev_hash, timestamp_str, user_str, action, details_str)

    entry = AuditLog(
        prev_hash=prev_hash,
        entry_hash=entry_hash,
        timestamp=now,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ai_generated=ai_generated,
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry


async def verify_chain(session: AsyncSession, limit: int = 1000) -> tuple[bool, int, str]:
    result = await session.execute(
        select(AuditLog).order_by(AuditLog.id.asc()).limit(limit)
    )
    entries = result.scalars().all()

    if not entries:
        return True, 0, ""

    expected_prev = "0" * 64
    for i, entry in enumerate(entries):
        if entry.prev_hash != expected_prev:
            return False, i, f"Entry {entry.id}: prev_hash mismatch at position {i}"

        recomputed = _compute_hash(
            entry.prev_hash,
            entry.timestamp.isoformat(),
            str(entry.user_id) if entry.user_id else "system",
            entry.action,
            json.dumps(entry.details, sort_keys=True, default=str) if entry.details else "",
        )
        if entry.entry_hash != recomputed:
            return False, i, f"Entry {entry.id}: hash mismatch at position {i}"

        expected_prev = entry.entry_hash

    return True, len(entries), ""
