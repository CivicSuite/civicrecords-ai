import uuid
from datetime import datetime, timezone

from civiccore.audit import (
    PersistedAuditLogEntry,
    ZERO_HASH,
    compute_persisted_audit_hash,
    verify_persisted_audit_chain,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


async def get_last_hash(session: AsyncSession, *, lock: bool = False) -> str:
    stmt = select(AuditLog.entry_hash).order_by(AuditLog.id.desc()).limit(1)
    if lock:
        stmt = stmt.with_for_update()
    result = await session.execute(stmt)
    last = result.scalar_one_or_none()
    return last if last else ZERO_HASH


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
    entry_hash = compute_persisted_audit_hash(
        previous_hash=prev_hash,
        timestamp=now.isoformat(),
        actor_id=user_id,
        action=action,
        details=details,
    )

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


def _persisted_entry(entry: AuditLog) -> PersistedAuditLogEntry:
    return PersistedAuditLogEntry(
        previous_hash=entry.prev_hash,
        entry_hash=entry.entry_hash,
        timestamp=entry.timestamp,
        actor_id=str(entry.user_id) if entry.user_id else None,
        action=entry.action,
        details=entry.details,
        entry_id=entry.id,
    )


async def verify_chain(session: AsyncSession) -> tuple[bool, int, str]:
    """Verify the full audit hash chain, paginating in batches of 1000.

    After archival/cleanup, the first surviving entry's prev_hash may point
    to a deleted entry. Verification starts from the first surviving row and
    then verifies every following link against the previous surviving hash.
    """

    batch_size = 1000
    total_checked = 0
    expected_prev: str | None = None
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

        if expected_prev is not None and entries[0].prev_hash != expected_prev:
            return (
                False,
                total_checked,
                f"Entry {entries[0].id}: prev_hash mismatch at position {total_checked}",
            )

        is_valid, batch_count, error = verify_persisted_audit_chain(
            (_persisted_entry(entry) for entry in entries),
            accept_first_previous_hash=True,
        )
        if not is_valid:
            return False, total_checked + batch_count, error

        total_checked += batch_count
        expected_prev = entries[-1].entry_hash
        last_id = entries[-1].id

    return True, total_checked, ""
