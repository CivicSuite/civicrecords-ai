from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import UserRole, require_role
from app.database import get_async_session
from app.models.request import RecordsRequest, RequestStatus
from app.schemas.analytics import OperationalMetrics

router = APIRouter(tags=["analytics"])


@router.get("/analytics/operational", response_model=OperationalMetrics)
async def get_operational_metrics(
    session: AsyncSession = Depends(get_async_session),
    user=Depends(require_role(UserRole.STAFF)),
):
    now = datetime.now(timezone.utc)

    # Requests by status
    status_result = await session.execute(
        select(RecordsRequest.status, func.count()).group_by(RecordsRequest.status)
    )
    by_status = {
        str(row[0].value) if hasattr(row[0], "value") else str(row[0]): row[1]
        for row in status_result.fetchall()
    }

    # Total open vs closed
    closed_statuses = {"fulfilled", "sent", "closed"}
    total_closed = sum(v for k, v in by_status.items() if k in closed_statuses)
    total_open = sum(v for k, v in by_status.items() if k not in closed_statuses)

    # Overdue — use text cast to avoid PostgreSQL enum mismatch
    from sqlalchemy import cast, String, text
    overdue_result = await session.execute(
        select(func.count()).where(
            RecordsRequest.statutory_deadline < now,
            cast(RecordsRequest.status, String).notin_(
                ["fulfilled", "sent", "closed"]
            ),
        )
    )
    total_overdue = overdue_result.scalar() or 0

    # Average response time (for closed requests with both dates)
    avg_result = await session.execute(
        select(
            func.avg(
                extract(
                    "epoch",
                    RecordsRequest.closed_at - RecordsRequest.date_received,
                )
                / 86400
            ),
        ).where(RecordsRequest.closed_at.isnot(None))
    )
    avg_days = avg_result.scalar()

    # Deadline compliance (closed requests that were closed before deadline)
    compliance_result = await session.execute(
        select(
            func.count().filter(
                RecordsRequest.closed_at <= RecordsRequest.statutory_deadline
            ),
            func.count(),
        ).where(
            RecordsRequest.closed_at.isnot(None),
            RecordsRequest.statutory_deadline.isnot(None),
        )
    )
    comp_row = compliance_result.fetchone()
    compliance_rate = (
        (comp_row[0] / comp_row[1] * 100)
        if comp_row and comp_row[1] > 0
        else 100.0
    )

    # Clarification frequency
    total_all = total_open + total_closed
    clarification_count = by_status.get("clarification_needed", 0)
    clarification_freq = (
        (clarification_count / total_all * 100) if total_all > 0 else 0.0
    )

    return OperationalMetrics(
        average_response_time_days=round(avg_days, 1) if avg_days else None,
        median_response_time_days=None,  # Requires window function, deferred
        requests_by_status=by_status,
        requests_by_department={},  # Populated once departments are assigned
        deadline_compliance_rate=round(compliance_rate, 1),
        total_open=total_open,
        total_closed=total_closed,
        total_overdue=total_overdue,
        clarification_frequency=round(clarification_freq, 1),
        top_request_topics=[],  # Populated via NLP in future
    )
