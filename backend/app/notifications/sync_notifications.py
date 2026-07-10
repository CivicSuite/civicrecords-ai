# backend/app/notifications/sync_notifications.py
"""Sync failure notifications: circuit-open + recovery, with 5-min digest batching."""
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_DIGEST_WINDOW_MINUTES = 5
_PENDING_CIRCUIT_OPENS: dict[str, datetime] = {}  # source_id → time opened in this window


async def notify_circuit_open(session: AsyncSession, source) -> None:
    """Notify admins that a source circuit has opened.

    Rate-limiting: multiple sources going circuit-open within the same 5-minute window
    are batched into a single 'Multiple sources paused' digest email.
    """
    now = datetime.now(timezone.utc)
    window_start = now.replace(second=0, microsecond=0) - timedelta(
        minutes=now.minute % _DIGEST_WINDOW_MINUTES
    )

    source_key = str(source.id)
    _PENDING_CIRCUIT_OPENS[source_key] = now

    in_window = {
        k: t for k, t in _PENDING_CIRCUIT_OPENS.items()
        if (now - t).total_seconds() < _DIGEST_WINDOW_MINUTES * 60
    }

    if len(in_window) == 1:
        await _queue_individual_circuit_open(session, source)
    else:
        await _queue_digest_notification(session, list(in_window.keys()), window_start)


async def notify_recovery(session: AsyncSession, source) -> None:
    """Notify admins that a source has recovered after circuit-open + unpause."""
    await _queue_recovery_notification(session, source)


async def _queue_individual_circuit_open(session, source):
    """Queue individual circuit-open notification."""
    logger.warning(
        "Circuit open: source '%s' paused after %d consecutive failures. Reason: %s",
        getattr(source, "name", str(getattr(source, "id", "unknown"))),
        getattr(source, "consecutive_failure_count", 0),
        getattr(source, "sync_paused_reason", ""),
    )
    try:
        from app.notifications.smtp_delivery import queue_notification
        await queue_notification(
            session=session,
            recipient_source_id=source.id,
            subject=f"CivicSunshine: Data source '{source.name}' paused",
            body=(
                f"Source '{source.name}' has been automatically paused after "
                f"{source.consecutive_failure_count} consecutive sync failures.\n"
                f"Reason: {source.sync_paused_reason}\n\n"
                f"Log in to the admin dashboard to investigate and unpause."
            ),
        )
    except Exception:
        logger.exception("Failed to queue circuit-open notification")


async def _queue_digest_notification(session, source_ids: list[str], window_start: datetime):
    """Queue a batched digest for multiple simultaneous circuit-opens."""
    logger.warning(
        "Circuit open digest: %d sources paused in window starting %s",
        len(source_ids), window_start.isoformat(),
    )
    try:
        from app.notifications.smtp_delivery import queue_notification
        await queue_notification(
            session=session,
            recipient_source_id=None,
            subject=f"CivicSunshine: {len(source_ids)} data sources paused",
            body=(
                f"{len(source_ids)} data sources were paused after consecutive sync failures.\n"
                f"Window: {window_start.strftime('%Y-%m-%d %H:%M UTC')}\n"
                f"Log in to the admin dashboard to investigate."
            ),
        )
    except Exception:
        logger.exception("Failed to queue digest circuit-open notification")


async def _queue_recovery_notification(session, source):
    """Queue a recovery notification after unpause + successful sync."""
    logger.info("Recovery: source '%s' synced after unpause", getattr(source, "name", ""))
    try:
        from app.notifications.smtp_delivery import queue_notification
        await queue_notification(
            session=session,
            recipient_source_id=source.id,
            subject=f"CivicSunshine: Data source '{source.name}' recovered",
            body=(
                f"Source '{source.name}' successfully synced after being unpaused.\n"
                f"Log in to view sync details."
            ),
        )
    except Exception:
        logger.exception("Failed to queue recovery notification")
