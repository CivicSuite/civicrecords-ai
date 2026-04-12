from app.worker import celery_app


@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(300.0, check_scheduled_sources.s(), name="check-scheduled-sources")


@celery_app.task(name="civicrecords.check_scheduled_sources")
def check_scheduled_sources():
    """Check for data sources with schedule_minutes set and trigger ingestion if due."""
    import asyncio
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from app.config import settings
    from app.models.document import DataSource

    async def _check():
        engine = create_async_engine(settings.database_url, echo=False)
        session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with session_maker() as session:
                result = await session.execute(
                    select(DataSource).where(
                        DataSource.is_active.is_(True),
                        DataSource.schedule_minutes.isnot(None),
                    )
                )
                sources = result.scalars().all()
                triggered = 0
                for source in sources:
                    now = datetime.now(timezone.utc)
                    if source.last_ingestion_at is None or \
                       (now - source.last_ingestion_at) > timedelta(minutes=source.schedule_minutes):
                        from app.ingestion.tasks import task_ingest_source
                        task_ingest_source.delay(source_id=str(source.id))
                        triggered += 1
                return {"checked": len(sources), "triggered": triggered}
        finally:
            await engine.dispose()

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_check())
    finally:
        loop.close()
