"""Core logic for deadline notification checks.

Called by Celery beat tasks in app/ingestion/scheduler.py.
Extracted as a standalone module so tests can call the async logic directly
without going through Celery task infrastructure.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.request import RecordsRequest, RequestStatus
from app.models.notifications import NotificationLog, NotificationTemplate
from app.models.user import User
from app.notifications.service import queue_notification

logger = logging.getLogger(__name__)

# Requests are considered "approaching" when the deadline is within this window.
APPROACHING_WINDOW_DAYS = 3

# Suppress duplicate notifications sent within this window.
DEDUP_HOURS = 23


async def _already_notified(
    session: AsyncSession,
    request_id,
    event_type: str,
) -> bool:
    """Return True if a notification for this request+event_type was sent in the last DEDUP_HOURS."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=DEDUP_HOURS)
    result = await session.execute(
        select(NotificationLog)
        .join(NotificationTemplate, NotificationLog.template_id == NotificationTemplate.id)
        .where(
            NotificationLog.request_id == request_id,
            NotificationTemplate.event_type == event_type,
            NotificationLog.created_at >= cutoff,
        )
    )
    return result.scalar_one_or_none() is not None


async def check_deadline_approaching(session: AsyncSession) -> dict:
    """Queue request_deadline_approaching notifications for requests due within 3 days.

    Skips requests that are FULFILLED or CLOSED, have no assigned_to user,
    or were already notified within the last 23 hours.

    Returns {"checked": int, "notified": int}.
    """
    now = datetime.now(timezone.utc)
    window_end = now + timedelta(days=APPROACHING_WINDOW_DAYS)

    result = await session.execute(
        select(RecordsRequest, User)
        .join(User, RecordsRequest.assigned_to == User.id)
        .where(
            RecordsRequest.statutory_deadline.isnot(None),
            RecordsRequest.statutory_deadline > now,
            RecordsRequest.statutory_deadline <= window_end,
            RecordsRequest.status.not_in(
                [RequestStatus.FULFILLED, RequestStatus.CLOSED]
            ),
        )
    )
    rows = result.all()

    notified = 0
    for req, assigned_user in rows:
        if await _already_notified(session, req.id, "request_deadline_approaching"):
            logger.debug(
                "Skipping duplicate approaching notification for request %s", req.id
            )
            continue

        await queue_notification(
            session=session,
            event_type="request_deadline_approaching",
            recipient_email=assigned_user.email,
            request_id=req.id,
            context_data={"request_id": str(req.id)},
        )
        notified += 1
        logger.info(
            "Queued deadline_approaching notification for request %s (deadline %s)",
            req.id,
            req.statutory_deadline.isoformat(),
        )

    return {"checked": len(rows), "notified": notified}


async def check_deadline_overdue(session: AsyncSession) -> dict:
    """Queue request_deadline_overdue notifications for requests past their deadline.

    Skips requests that are FULFILLED or CLOSED, have no assigned_to user,
    or were already notified within the last 23 hours.

    Returns {"checked": int, "notified": int}.
    """
    now = datetime.now(timezone.utc)

    result = await session.execute(
        select(RecordsRequest, User)
        .join(User, RecordsRequest.assigned_to == User.id)
        .where(
            RecordsRequest.statutory_deadline.isnot(None),
            RecordsRequest.statutory_deadline <= now,
            RecordsRequest.status.not_in(
                [RequestStatus.FULFILLED, RequestStatus.CLOSED]
            ),
        )
    )
    rows = result.all()

    notified = 0
    for req, assigned_user in rows:
        if await _already_notified(session, req.id, "request_deadline_overdue"):
            logger.debug(
                "Skipping duplicate overdue notification for request %s", req.id
            )
            continue

        await queue_notification(
            session=session,
            event_type="request_deadline_overdue",
            recipient_email=assigned_user.email,
            request_id=req.id,
            context_data={"request_id": str(req.id)},
        )
        notified += 1
        logger.info(
            "Queued deadline_overdue notification for request %s (deadline %s)",
            req.id,
            req.statutory_deadline.isoformat(),
        )

    return {"checked": len(rows), "notified": notified}
