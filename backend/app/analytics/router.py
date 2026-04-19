from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import UserRole, require_role
from app.database import get_async_session
from app.models.request import RecordsRequest, RequestStatus
from app.schemas.analytics import OperationalMetrics

router = APIRouter(tags=["analytics"])


def _request_dept_predicate(user):
    """Return the SQLAlchemy predicate limiting RecordsRequest to the caller's
    department, fail-closed. Admin bypass returns ``None`` meaning "no filter".

    Non-admin users without a department assignment are rejected with 403 so
    aggregate metrics never leak a cross-department total.
    """
    if user.role == UserRole.ADMIN:
        return None
    if user.department_id is None:
        raise HTTPException(
            status_code=403,
            detail="Access denied: user is not assigned to a department",
        )
    return RecordsRequest.department_id == user.department_id


@router.get("/analytics/operational", response_model=OperationalMetrics)
async def get_operational_metrics(
    session: AsyncSession = Depends(get_async_session),
    user=Depends(require_role(UserRole.STAFF)),
):
    now = datetime.now(timezone.utc)
    dept_pred = _request_dept_predicate(user)

    # Requests by status
    status_stmt = select(RecordsRequest.status, func.count()).group_by(RecordsRequest.status)
    if dept_pred is not None:
        status_stmt = status_stmt.where(dept_pred)
    status_result = await session.execute(status_stmt)
    by_status = {
        str(row[0].value) if hasattr(row[0], "value") else str(row[0]): row[1]
        for row in status_result.fetchall()
    }

    # Total open vs closed
    closed_statuses = {"fulfilled", "closed"}
    total_closed = sum(v for k, v in by_status.items() if k in closed_statuses)
    total_open = sum(v for k, v in by_status.items() if k not in closed_statuses)

    # Overdue — use text cast to avoid PostgreSQL enum mismatch
    from sqlalchemy import cast, String, text
    overdue_stmt = select(func.count()).where(
        RecordsRequest.statutory_deadline < now,
        cast(RecordsRequest.status, String).notin_(["fulfilled", "closed"]),
    )
    if dept_pred is not None:
        overdue_stmt = overdue_stmt.where(dept_pred)
    overdue_result = await session.execute(overdue_stmt)
    total_overdue = overdue_result.scalar() or 0

    # Average response time (for closed requests with both dates)
    avg_stmt = select(
        func.avg(
            extract(
                "epoch",
                RecordsRequest.closed_at - RecordsRequest.date_received,
            )
            / 86400
        ),
    ).where(RecordsRequest.closed_at.isnot(None))
    if dept_pred is not None:
        avg_stmt = avg_stmt.where(dept_pred)
    avg_result = await session.execute(avg_stmt)
    avg_days = avg_result.scalar()

    # Deadline compliance (closed requests that were closed before deadline)
    compliance_stmt = select(
        func.count().filter(
            RecordsRequest.closed_at <= RecordsRequest.statutory_deadline
        ),
        func.count(),
    ).where(
        RecordsRequest.closed_at.isnot(None),
        RecordsRequest.statutory_deadline.isnot(None),
    )
    if dept_pred is not None:
        compliance_stmt = compliance_stmt.where(dept_pred)
    compliance_result = await session.execute(compliance_stmt)
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
