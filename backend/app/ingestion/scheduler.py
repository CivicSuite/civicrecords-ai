from app.worker import celery_app


@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(300.0, check_scheduled_sources.s(), name="check-scheduled-sources")
    # Run audit retention cleanup daily (86400 seconds)
    sender.add_periodic_task(86400.0, cleanup_audit_logs.s(), name="audit-retention-cleanup")
    # Deliver queued email notifications every 60 seconds
    sender.add_periodic_task(60.0, deliver_notifications.s(), name="deliver-notifications")
    # Check for approaching and overdue request deadlines once per day
    sender.add_periodic_task(
        86400.0,
        check_deadline_approaching_task.s(),
        name="check-deadline-approaching",
    )
    sender.add_periodic_task(
        86400.0,
        check_deadline_overdue_task.s(),
        name="check-deadline-overdue",
    )


@celery_app.task(name="civicrecords.check_scheduled_sources")
def check_scheduled_sources():
    """Check each active, non-paused source with a cron schedule and trigger if overdue."""
    import asyncio
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from app.config import settings

    async def _check():
        engine = create_async_engine(settings.database_url, echo=False)
        session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with session_maker() as session:
                return await _check_scheduled_sources_async(session)
        finally:
            await engine.dispose()

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_check())
    finally:
        loop.close()


async def _check_scheduled_sources_async(session) -> dict:
    """Core scheduling logic, extracted for testability.

    anchor = source.last_sync_at or epoch
    next_scheduled = croniter(expr, anchor).get_next(datetime)
    trigger if next_scheduled <= now()
    """
    from datetime import datetime, timezone
    from sqlalchemy import select
    from croniter import croniter
    from app.models.document import DataSource
    from app.ingestion.tasks import task_ingest_source

    UTC = timezone.utc

    result = await session.execute(
        select(DataSource).where(
            DataSource.is_active.is_(True),
            DataSource.schedule_enabled.is_(True),
            DataSource.sync_paused.is_(False),
            DataSource.sync_schedule.isnot(None),
        )
    )
    sources = result.scalars().all()
    now = datetime.now(UTC)
    triggered = 0

    for source in sources:
        anchor = source.last_sync_at or datetime(1970, 1, 1, tzinfo=UTC)
        it = croniter(source.sync_schedule, anchor)
        next_scheduled = it.get_next(datetime)
        if next_scheduled <= now:
            task_ingest_source.delay(str(source.id))
            triggered += 1

    return {"checked": len(sources), "triggered": triggered}


@celery_app.task(name="civicrecords.cleanup_audit_logs")
def cleanup_audit_logs():
    """Archive and then delete audit log entries older than the configured retention period."""
    import asyncio
    import json
    import os
    from datetime import datetime, timezone, timedelta
    from pathlib import Path
    from sqlalchemy import delete, select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from app.config import settings
    from app.models.audit import AuditLog

    async def _cleanup():
        engine = create_async_engine(settings.database_url, echo=False)
        session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with session_maker() as session:
                cutoff = datetime.now(timezone.utc) - timedelta(days=settings.audit_retention_days)

                # Fetch entries to be archived before deleting
                result = await session.execute(
                    select(AuditLog)
                    .where(AuditLog.timestamp < cutoff)
                    .order_by(AuditLog.timestamp.asc(), AuditLog.id.asc())
                )
                entries = result.scalars().all()

                if not entries:
                    return {"archived": 0, "deleted": 0, "cutoff": cutoff.isoformat()}

                # Build archive data
                archive_entries = []
                for entry in entries:
                    archive_entries.append({
                        "id": entry.id,
                        "user_id": str(entry.user_id) if entry.user_id else None,
                        "action": entry.action,
                        "resource_type": entry.resource_type,
                        "resource_id": entry.resource_id,
                        "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
                        "prev_hash": entry.prev_hash,
                        "entry_hash": entry.entry_hash,
                    })

                # Determine date range for filename
                earliest = entries[0].timestamp.strftime("%Y-%m-%d")
                latest = entries[-1].timestamp.strftime("%Y-%m-%d")

                # Write archive file
                archive_dir = Path("/data/cache/audit-archives")
                archive_dir.mkdir(parents=True, exist_ok=True)
                archive_path = archive_dir / f"audit_archive_{earliest}_to_{latest}.json"
                with open(archive_path, "w", encoding="utf-8") as f:
                    json.dump(archive_entries, f, indent=2, default=str)

                # Delete after successful archival
                del_result = await session.execute(
                    delete(AuditLog).where(AuditLog.timestamp < cutoff)
                )
                await session.commit()
                return {
                    "archived": len(archive_entries),
                    "deleted": del_result.rowcount,
                    "archive_file": str(archive_path),
                    "cutoff": cutoff.isoformat(),
                }
        finally:
            await engine.dispose()

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_cleanup())
    finally:
        loop.close()


@celery_app.task(name="civicrecords.deliver_notifications")
def deliver_notifications():
    """Send queued email notifications via SMTP."""
    import asyncio
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from app.config import settings
    from app.notifications.smtp_delivery import deliver_queued_notifications

    async def _deliver():
        engine = create_async_engine(settings.database_url, echo=False)
        session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with session_maker() as session:
                return await deliver_queued_notifications(session)
        finally:
            await engine.dispose()

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_deliver())
    finally:
        loop.close()


@celery_app.task(name="civicrecords.check_deadline_approaching")
def check_deadline_approaching_task():
    """Celery beat wrapper: queue deadline_approaching notifications."""
    import asyncio
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from app.config import settings
    from app.requests.deadline_check import check_deadline_approaching

    async def _run():
        engine = create_async_engine(settings.database_url, echo=False)
        session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with session_maker() as session:
                result = await check_deadline_approaching(session)
                await session.commit()
                return result
        finally:
            await engine.dispose()

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()


@celery_app.task(name="civicrecords.check_deadline_overdue")
def check_deadline_overdue_task():
    """Celery beat wrapper: queue deadline_overdue notifications."""
    import asyncio
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from app.config import settings
    from app.requests.deadline_check import check_deadline_overdue

    async def _run():
        engine = create_async_engine(settings.database_url, echo=False)
        session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with session_maker() as session:
                result = await check_deadline_overdue(session)
                await session.commit()
                return result
        finally:
            await engine.dispose()

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()
