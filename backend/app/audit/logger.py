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


async def get_last_hash(session: AsyncSession, *, lock: bool = False) -> str:
    stmt = select(AuditLog.entry_hash).order_by(AuditLog.id.desc()).limit(1)
    if lock:
        stmt = stmt.with_for_update()
    result = await session.execute(stmt)
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
    prev_hash = await get_last_hash(session, lock=True)
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


async def verify_chain(session: AsyncSession) -> tuple[bool, int, str]:
    """Verify the full audit hash chain, paginating in batches of 1000.

    After archival/cleanup, the first surviving entry's prev_hash may point
    to a deleted entry — verification starts from whatever the first entry is
    and verifies forward from there.
    """
    batch_size = 1000
    total_checked = 0
    expected_prev: str | None = None  # Will be set from first entry
    last_id = 0

    while True:
        result = await session.execute(
            select(AuditLog)
            .where(AuditLog.id > last_id)
            .order_by(AuditLog.timestamp.asc(), AuditLog.id.asc())
            .limit(batch_size)
        )
        entries = result.scalars().all()

        if not entries:
            break

        for entry in entries:
            if expected_prev is None:
                # First surviving entry — accept its prev_hash as the starting point
                expected_prev = entry.prev_hash
            else:
                if entry.prev_hash != expected_prev:
                    return False, total_checked, f"Entry {entry.id}: prev_hash mismatch at position {total_checked}"

            recomputed = _compute_hash(
                entry.prev_hash,
                entry.timestamp.isoformat(),
                str(entry.user_id) if entry.user_id else "system",
                entry.action,
                json.dumps(entry.details, sort_keys=True, default=str) if entry.details else "",
            )
            if entry.entry_hash != recomputed:
                return False, total_checked, f"Entry {entry.id}: hash mismatch at position {total_checked}"

            expected_prev = entry.entry_hash
            total_checked += 1
            last_id = entry.id

    return True, total_checked, ""
