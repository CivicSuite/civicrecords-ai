# backend/app/ingestion/sync_runner.py
"""P7 sync runner: two-layer retry, circuit breaker, partial-advance cursor, run log."""
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import DataSource
from app.models.sync_failure import SyncFailure, SyncRunLog
from app.ingestion.pipeline import ingest_structured_record

logger = logging.getLogger(__name__)

UTC = timezone.utc
_DEFAULT_RETRY_BATCH_SIZE = 100
_DEFAULT_RETRY_TIME_LIMIT_SECONDS = 90
_CIRCUIT_OPEN_THRESHOLD = 5
_DEAD_LETTER_MAX_RETRIES = 5
_DEAD_LETTER_MAX_AGE_DAYS = 7


async def run_connector_sync_with_retry(
    connector,
    source_id: str,
    session: AsyncSession,
) -> dict[str, Any]:
    """Run a full connector sync cycle with two-layer retry and circuit breaker.

    Returns dict: {discovered, succeeded, failed, retries_attempted, run_id}
    """
    source = await session.get(
        DataSource, uuid.UUID(source_id) if isinstance(source_id, str) else source_id
    )
    if not source:
        raise ValueError(f"DataSource not found: {source_id}")

    connector_type = (
        source.source_type.value if hasattr(source.source_type, "value") else str(source.source_type)
    )
    is_structured = connector_type in ("rest_api", "odbc")
    batch_size = source.retry_batch_size or _DEFAULT_RETRY_BATCH_SIZE
    time_limit = source.retry_time_limit_seconds or _DEFAULT_RETRY_TIME_LIMIT_SECONDS

    run_log = SyncRunLog(source_id=source.id, started_at=datetime.now(UTC))
    session.add(run_log)
    await session.flush()

    succeeded = 0
    failed = 0
    retries_attempted = 0
    any_success = False
    discovered_count = 0
    retry_start = datetime.now(UTC)

    try:
        # === Layer 2: record-level retry (process BEFORE discover) ===
        retrying_rows_result = await session.execute(
            select(SyncFailure).where(
                SyncFailure.source_id == source.id,
                SyncFailure.status == "retrying",
            ).limit(batch_size)
        )
        retrying_rows = retrying_rows_result.scalars().all()

        for failure in retrying_rows:
            if (datetime.now(UTC) - retry_start).total_seconds() > time_limit:
                break

            retries_attempted += 1
            now = datetime.now(UTC)

            age = now - failure.first_failed_at
            if failure.retry_count >= _DEAD_LETTER_MAX_RETRIES or age > timedelta(days=_DEAD_LETTER_MAX_AGE_DAYS):
                failure.status = "permanently_failed"
                await session.flush()
                continue

            try:
                fetched = await connector.fetch(failure.source_path)

                if is_structured:
                    await _ingest_structured(session, source, connector_type, fetched)
                else:
                    from app.ingestion.tasks import ingest_file_from_bytes
                    await ingest_file_from_bytes(
                        session=session,
                        content=fetched.content,
                        filename=fetched.filename,
                        file_type=fetched.file_type,
                        source_id=source.id,
                    )

                failure.status = "resolved"
                failure.resolved_at = now
                succeeded += 1
                any_success = True

            except FileNotFoundError:
                failure.status = "tombstone"
                failure.last_retried_at = now
            except Exception as exc:
                failure.retry_count += 1
                failure.last_retried_at = now
                failure.error_message = str(exc)[:500]
                failure.error_class = type(exc).__name__

                if failure.retry_count >= _DEAD_LETTER_MAX_RETRIES:
                    failure.status = "permanently_failed"
                failed += 1

            await session.flush()

        # === Discover new records ===
        discovered_records = await connector.discover()
        discovered_count = len(discovered_records)

        if discovered_count == 0 and retries_attempted == 0:
            run_log.finished_at = datetime.now(UTC)
            run_log.status = "success"
            run_log.records_attempted = 0
            run_log.records_succeeded = 0
            run_log.records_failed = 0
            await session.commit()
            return {
                "discovered": 0, "succeeded": succeeded, "failed": failed,
                "retries_attempted": retries_attempted, "run_id": str(run_log.id),
            }

        last_successful_modified: datetime | None = None

        for record in discovered_records:
            try:
                fetched = await connector.fetch(record.source_path)

                if is_structured:
                    await _ingest_structured(session, source, connector_type, fetched)
                else:
                    from app.ingestion.tasks import ingest_file_from_bytes
                    await ingest_file_from_bytes(
                        session=session,
                        content=fetched.content,
                        filename=fetched.filename,
                        file_type=fetched.file_type,
                        source_id=source.id,
                    )

                succeeded += 1
                any_success = True
                if record.last_modified:
                    last_successful_modified = record.last_modified

            except Exception as exc:
                import sqlalchemy.exc
                error_class = type(exc).__name__

                failure_status = "retrying"
                if isinstance(exc, sqlalchemy.exc.IntegrityError):
                    failure_status = "permanently_failed"
                elif getattr(exc, "response", None) and getattr(exc.response, "status_code", None) == 404:
                    failure_status = "tombstone"

                failure = SyncFailure(
                    source_id=source.id,
                    source_path=record.source_path,
                    error_message=str(exc)[:500],
                    error_class=error_class,
                    http_status_code=getattr(getattr(exc, "response", None), "status_code", None),
                    status=failure_status,
                )
                session.add(failure)
                failed += 1
                logger.error(
                    "Record fetch failed",
                    extra={"source_id": str(source.id), "path": record.source_path, "error": str(exc)},
                )

        await session.flush()

        # === Cursor advance (partial-safe) ===
        source.last_sync_at = datetime.now(UTC)
        source.last_sync_cursor = (
            last_successful_modified.isoformat()
            if last_successful_modified
            else datetime.now(UTC).isoformat()
        )

        # === Circuit breaker counter update ===
        if any_success:
            source.consecutive_failure_count = 0
            source.last_sync_status = "partial" if failed > 0 else "success"
            if source.sync_paused_reason == "grace_period":
                source.sync_paused_reason = None
        elif failed > 0 and not any_success:
            source.consecutive_failure_count += 1
            source.last_error_at = datetime.now(UTC)
            source.last_sync_status = "failed"

            threshold = 2 if source.sync_paused_reason == "grace_period" else _CIRCUIT_OPEN_THRESHOLD
            if source.consecutive_failure_count >= threshold:
                source.sync_paused = True
                source.sync_paused_at = datetime.now(UTC)
                source.sync_paused_reason = (
                    f"Circuit open after {source.consecutive_failure_count} consecutive full-run failures"
                )
                await _fire_circuit_open_notification(session, source)

        # === Update run log ===
        run_log.finished_at = datetime.now(UTC)
        run_log.status = source.last_sync_status
        run_log.records_attempted = discovered_count + retries_attempted
        run_log.records_succeeded = succeeded
        run_log.records_failed = failed

        await session.commit()

    finally:
        connector.close()

    return {
        "discovered": discovered_count,
        "succeeded": succeeded,
        "failed": failed,
        "retries_attempted": retries_attempted,
        "run_id": str(run_log.id),
    }


async def _ingest_structured(session, source, connector_type, fetched):
    """Route to ingest_structured_record with correct args."""
    await ingest_structured_record(
        session=session,
        source_id=source.id,
        source_path=fetched.source_path,
        content_bytes=fetched.content,
        filename=fetched.filename,
        metadata=fetched.metadata,
        connector_type=connector_type,
    )


async def _fire_circuit_open_notification(session, source):
    """Fire circuit-open notification (rate-limited: 5-min digest window)."""
    try:
        from app.notifications.sync_notifications import notify_circuit_open
        await notify_circuit_open(session, source)
    except Exception:
        logger.exception("Failed to send circuit-open notification for source %s", source.id)
