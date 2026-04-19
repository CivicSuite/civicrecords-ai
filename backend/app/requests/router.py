import uuid
from datetime import datetime, timezone, timedelta

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.logger import write_audit_log
from app.notifications.service import queue_notification
from app.config import settings
from app.auth.dependencies import require_role, check_department_access, require_department_scope
from app.database import get_async_session
from app.models.city_profile import CityProfile
from app.models.document import Document
from app.models.request import (
    DocumentCache, InclusionStatus, RecordsRequest, RequestDocument, RequestStatus,
)
from app.models.request_workflow import RequestTimeline, RequestMessage, ResponseLetter
from app.models.user import User, UserRole
from app.schemas.request import (
    FeeLineItemCreate, FeeLineItemRead,
    MessageCreate, MessageRead,
    RequestCreate, RequestDocumentAdd, RequestDocumentRead,
    RequestRead, RequestStats, RequestUpdate,
    ResponseLetterCreate, ResponseLetterRead, ResponseLetterUpdate,
    TimelineEventCreate, TimelineEventRead,
)

router = APIRouter(prefix="/requests", tags=["requests"])

logger = logging.getLogger(__name__)


async def _get_city_name(session: AsyncSession) -> str:
    """Fetch the configured city name for notification templates."""
    result = await session.execute(select(CityProfile).limit(1))
    profile = result.scalar_one_or_none()
    return profile.city_name if profile else "Records Office"

# Valid status transitions
VALID_TRANSITIONS = {
    RequestStatus.RECEIVED: {RequestStatus.CLARIFICATION_NEEDED, RequestStatus.ASSIGNED, RequestStatus.SEARCHING},
    RequestStatus.CLARIFICATION_NEEDED: {RequestStatus.RECEIVED, RequestStatus.ASSIGNED, RequestStatus.SEARCHING},
    RequestStatus.ASSIGNED: {RequestStatus.SEARCHING, RequestStatus.CLARIFICATION_NEEDED},
    RequestStatus.SEARCHING: {RequestStatus.IN_REVIEW, RequestStatus.DRAFTED, RequestStatus.CLARIFICATION_NEEDED},
    RequestStatus.IN_REVIEW: {RequestStatus.DRAFTED, RequestStatus.READY_FOR_RELEASE, RequestStatus.SEARCHING},
    RequestStatus.READY_FOR_RELEASE: {RequestStatus.DRAFTED, RequestStatus.IN_REVIEW, RequestStatus.APPROVED},
    RequestStatus.DRAFTED: {RequestStatus.IN_REVIEW, RequestStatus.APPROVED},
    RequestStatus.APPROVED: {RequestStatus.FULFILLED},
    RequestStatus.FULFILLED: {RequestStatus.CLOSED},  # can only close
    RequestStatus.CLOSED: set(),  # terminal state — no transitions out
}


async def log_timeline(
    session: AsyncSession,
    request_id: uuid.UUID,
    event_type: str,
    description: str,
    actor_id: uuid.UUID,
    actor_role: str,
    internal_note: str | None = None,
):
    entry = RequestTimeline(
        request_id=request_id,
        event_type=event_type,
        actor_id=actor_id,
        actor_role=actor_role,
        description=description,
        internal_note=internal_note,
    )
    session.add(entry)


@router.post("/", response_model=RequestRead, status_code=201)
async def create_request(
    data: RequestCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    # Department: use explicit value if admin, otherwise use user's department
    dept_id = data.department_id
    if user.role != UserRole.ADMIN:
        dept_id = user.department_id  # Staff always uses their own department

    req = RecordsRequest(
        requester_name=data.requester_name,
        requester_email=data.requester_email,
        requester_phone=data.requester_phone,
        requester_type=data.requester_type,
        description=data.description,
        statutory_deadline=data.statutory_deadline,
        scope_assessment=data.scope_assessment,
        priority=data.priority,
        created_by=user.id,
        assigned_to=user.id,
        department_id=dept_id,
    )
    session.add(req)
    await session.commit()
    await session.refresh(req)

    # Dispatch request_received notification if requester provided an email.
    # Mirrors the pattern in update_request (PATCH dispatch).
    if req.requester_email:
        city_name = await _get_city_name(session)
        await queue_notification(
            session=session,
            event_type="request_received",
            recipient_email=req.requester_email,
            request_id=req.id,
            context_data={
                "requester_name": req.requester_name,
                "request_id": str(req.id),
                "status": req.status.value,
                "city_name": city_name,
            },
        )

    await write_audit_log(
        session=session, action="create_request", resource_type="request",
        resource_id=str(req.id), user_id=user.id,
        details={"requester": data.requester_name, "description": data.description[:100]},
    )
    return req


@router.get("/", response_model=list[RequestRead])
async def list_requests(
    status: RequestStatus | None = None,
    assigned_to: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.LIAISON)),
):
    stmt = select(RecordsRequest).order_by(RecordsRequest.created_at.desc())

    # Department scoping: non-admins see only their department
    if user.role != UserRole.ADMIN and user.department_id is not None:
        stmt = stmt.where(RecordsRequest.department_id == user.department_id)

    if status:
        stmt = stmt.where(RecordsRequest.status == status)
    if assigned_to:
        stmt = stmt.where(RecordsRequest.assigned_to == assigned_to)
    stmt = stmt.offset(offset).limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/stats", response_model=RequestStats)
async def request_stats(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.LIAISON)),
):
    dept_filter = []
    if user.role != UserRole.ADMIN and user.department_id is not None:
        dept_filter = [RecordsRequest.department_id == user.department_id]

    total = (await session.execute(
        select(func.count(RecordsRequest.id)).where(*dept_filter)
    )).scalar() or 0

    by_status = {}
    for s in RequestStatus:
        count = (await session.execute(
            select(func.count(RecordsRequest.id)).where(
                RecordsRequest.status == s, *dept_filter
            )
        )).scalar() or 0
        by_status[s.value] = count

    now = datetime.now(timezone.utc)
    three_days = now + timedelta(days=3)

    approaching = (await session.execute(
        select(func.count(RecordsRequest.id)).where(
            RecordsRequest.statutory_deadline.isnot(None),
            RecordsRequest.statutory_deadline <= three_days,
            RecordsRequest.statutory_deadline > now,
            RecordsRequest.status.notin_([RequestStatus.FULFILLED, RequestStatus.CLOSED]),
            *dept_filter,
        )
    )).scalar() or 0

    overdue = (await session.execute(
        select(func.count(RecordsRequest.id)).where(
            RecordsRequest.statutory_deadline.isnot(None),
            RecordsRequest.statutory_deadline < now,
            RecordsRequest.status.notin_([RequestStatus.FULFILLED, RequestStatus.CLOSED]),
            *dept_filter,
        )
    )).scalar() or 0

    return RequestStats(
        total_requests=total, by_status=by_status,
        approaching_deadline=approaching, overdue=overdue,
    )


@router.get("/{request_id}", response_model=RequestRead)
async def get_request(
    request_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.LIAISON)),
):
    req = await session.get(RecordsRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    check_department_access(user, req.department_id)
    return req


@router.patch("/{request_id}", response_model=RequestRead)
async def update_request(
    request_id: uuid.UUID,
    data: RequestUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    req = await session.get(RecordsRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    check_department_access(user, req.department_id)

    if data.status is not None and data.status != req.status:
        valid = VALID_TRANSITIONS.get(req.status, set())
        if data.status not in valid:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot transition from {req.status.value} to {data.status.value}",
            )
        req.status = data.status
        if data.status in (RequestStatus.FULFILLED, RequestStatus.CLOSED):
            req.closed_at = datetime.now(timezone.utc)
        await log_timeline(session, request_id, "status_change",
                          f"Status changed to {data.status.value}", user.id, user.role)
        # Dispatch notification if template exists for this event
        if req.requester_email:
            city_name = await _get_city_name(session)
            await queue_notification(
                session=session,
                event_type=f"request_{data.status.value}",
                recipient_email=req.requester_email,
                request_id=request_id,
                context_data={
                    "requester_name": req.requester_name,
                    "request_id": str(request_id),
                    "status": data.status.value,
                    "city_name": city_name,
                },
            )

    if data.description is not None:
        req.description = data.description
    if data.assigned_to is not None:
        req.assigned_to = data.assigned_to
    if data.response_draft is not None:
        req.response_draft = data.response_draft
    if data.statutory_deadline is not None:
        req.statutory_deadline = data.statutory_deadline
    if data.scope_assessment is not None:
        req.scope_assessment = data.scope_assessment

    await session.commit()
    await session.refresh(req)

    await write_audit_log(
        session=session, action="update_request", resource_type="request",
        resource_id=str(req.id), user_id=user.id,
        details=data.model_dump(exclude_none=True),
    )
    return req


@router.post("/{request_id}/documents", response_model=RequestDocumentRead, status_code=201)
async def attach_document(
    request_id: uuid.UUID,
    data: RequestDocumentAdd,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    req = await session.get(RecordsRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    check_department_access(user, req.department_id)

    doc = await session.get(Document, data.document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Check not already attached
    existing = await session.execute(
        select(RequestDocument).where(
            RequestDocument.request_id == request_id,
            RequestDocument.document_id == data.document_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Document already attached")

    req_doc = RequestDocument(
        request_id=request_id,
        document_id=data.document_id,
        relevance_note=data.relevance_note,
        attached_by=user.id,
    )
    session.add(req_doc)

    # Cache document for legal defensibility
    if doc.source_path:
        import asyncio
        import shutil
        from pathlib import Path

        cache_dir = Path("/data/cache") / str(request_id)
        cache_dir.mkdir(parents=True, exist_ok=True)
        source = Path(doc.source_path)
        if source.exists():
            dest = cache_dir / f"{doc.id}_{source.name}"
            await asyncio.to_thread(shutil.copy2, str(source), str(dest))
            cache_entry = DocumentCache(
                document_id=doc.id,
                request_id=request_id,
                cached_file_path=str(dest),
                file_size=dest.stat().st_size,
            )
            session.add(cache_entry)

    await session.commit()
    await session.refresh(req_doc)

    await write_audit_log(
        session=session, action="attach_document", resource_type="request",
        resource_id=str(request_id), user_id=user.id,
        details={"document_id": str(data.document_id), "filename": doc.filename},
    )
    return req_doc


@router.get("/{request_id}/documents", response_model=list[RequestDocumentRead])
async def list_attached_documents(
    request_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    # NOTE: Documents require STAFF — liaison can see request metadata but not attachments
    user: User = Depends(require_role(UserRole.STAFF)),
):
    req = await session.get(RecordsRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    check_department_access(user, req.department_id)

    result = await session.execute(
        select(RequestDocument).where(RequestDocument.request_id == request_id)
        .order_by(RequestDocument.attached_at)
    )
    return result.scalars().all()


@router.delete("/{request_id}/documents/{doc_id}", status_code=204)
async def remove_document(
    request_id: uuid.UUID,
    doc_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    req = await session.get(RecordsRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    check_department_access(user, req.department_id)

    result = await session.execute(
        select(RequestDocument).where(
            RequestDocument.request_id == request_id,
            RequestDocument.document_id == doc_id,
        )
    )
    req_doc = result.scalar_one_or_none()
    if not req_doc:
        raise HTTPException(status_code=404, detail="Attachment not found")

    await session.delete(req_doc)
    await session.commit()

    await write_audit_log(
        session=session, action="remove_document", resource_type="request",
        resource_id=str(request_id), user_id=user.id,
        details={"document_id": str(doc_id)},
    )


@router.post("/{request_id}/submit-review", response_model=RequestRead)
async def submit_for_review(
    request_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    req = await session.get(RecordsRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    check_department_access(user, req.department_id)

    if req.status not in (RequestStatus.SEARCHING, RequestStatus.DRAFTED):
        raise HTTPException(status_code=400, detail=f"Cannot submit for review from status {req.status.value}")

    req.status = RequestStatus.IN_REVIEW
    await log_timeline(session, request_id, "status_change",
                      "Submitted for review", user.id, user.role)
    # Dispatch notification if template exists for this event
    if req.requester_email:
        city_name = await _get_city_name(session)
        await queue_notification(
            session=session,
            event_type="request_in_review",
            recipient_email=req.requester_email,
            request_id=request_id,
            context_data={
                "requester_name": req.requester_name,
                "request_id": str(request_id),
                "status": "in_review",
                "city_name": city_name,
            },
        )
    await session.commit()
    await session.refresh(req)

    await write_audit_log(
        session=session, action="submit_for_review", resource_type="request",
        resource_id=str(request_id), user_id=user.id,
    )
    return req


@router.post("/{request_id}/ready-for-release", response_model=RequestRead)
async def mark_ready_for_release(
    request_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.REVIEWER)),
):
    req = await session.get(RecordsRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    check_department_access(user, req.department_id)

    if req.status != RequestStatus.IN_REVIEW:
        raise HTTPException(status_code=400, detail=f"Can only mark ready for release from 'in_review' status, current: {req.status.value}")

    req.status = RequestStatus.READY_FOR_RELEASE
    await log_timeline(session, request_id, "status_change",
                      "Marked ready for release", user.id, user.role)
    # Dispatch notification if template exists for this event
    if req.requester_email:
        city_name = await _get_city_name(session)
        await queue_notification(
            session=session,
            event_type="request_ready_for_release",
            recipient_email=req.requester_email,
            request_id=request_id,
            context_data={
                "requester_name": req.requester_name,
                "request_id": str(request_id),
                "status": "ready_for_release",
                "city_name": city_name,
            },
        )
    await session.commit()
    await session.refresh(req)

    await write_audit_log(
        session=session, action="ready_for_release", resource_type="request",
        resource_id=str(request_id), user_id=user.id,
    )
    return req


@router.post("/{request_id}/approve", response_model=RequestRead)
async def approve_request(
    request_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.REVIEWER)),
):
    req = await session.get(RecordsRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    check_department_access(user, req.department_id)

    if req.status not in (RequestStatus.DRAFTED, RequestStatus.READY_FOR_RELEASE):
        raise HTTPException(status_code=400, detail=f"Can only approve from 'drafted' or 'ready_for_release' status, current: {req.status.value}")

    req.status = RequestStatus.APPROVED
    await log_timeline(session, request_id, "response_approved",
                      "Request approved", user.id, user.role)
    # Dispatch notification if template exists for this event
    if req.requester_email:
        city_name = await _get_city_name(session)
        await queue_notification(
            session=session,
            event_type="request_approved",
            recipient_email=req.requester_email,
            request_id=request_id,
            context_data={
                "requester_name": req.requester_name,
                "request_id": str(request_id),
                "status": "approved",
                "city_name": city_name,
            },
        )
    await session.commit()
    await session.refresh(req)

    await write_audit_log(
        session=session, action="approve_request", resource_type="request",
        resource_id=str(request_id), user_id=user.id,
    )
    return req


@router.post("/{request_id}/reject", response_model=RequestRead)
async def reject_request(
    request_id: uuid.UUID,
    reason: str = "",
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.REVIEWER)),
):
    req = await session.get(RecordsRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    check_department_access(user, req.department_id)

    if req.status != RequestStatus.IN_REVIEW:
        raise HTTPException(status_code=400, detail="Can only reject from 'in_review' status")

    req.status = RequestStatus.DRAFTED
    req.review_notes = reason if reason else None
    await log_timeline(session, request_id, "status_change",
                      "Request rejected — returned for revision", user.id, user.role,
                      internal_note=reason if reason else None)
    # Dispatch notification if template exists for this event
    if req.requester_email:
        city_name = await _get_city_name(session)
        await queue_notification(
            session=session,
            event_type="request_drafted",
            recipient_email=req.requester_email,
            request_id=request_id,
            context_data={
                "requester_name": req.requester_name,
                "request_id": str(request_id),
                "status": "drafted",
                "city_name": city_name,
            },
        )
    await session.commit()
    await session.refresh(req)

    await write_audit_log(
        session=session, action="reject_request", resource_type="request",
        resource_id=str(request_id), user_id=user.id,
        details={"reason": reason},
    )
    return req


@router.get("/{request_id}/timeline", response_model=list[TimelineEventRead])
async def get_timeline(
    request_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    req = await session.get(RecordsRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    require_department_scope(user, req.department_id)

    result = await session.execute(
        select(RequestTimeline)
        .where(RequestTimeline.request_id == request_id)
        .order_by(RequestTimeline.created_at.desc())
    )
    return result.scalars().all()


@router.post("/{request_id}/timeline", response_model=TimelineEventRead, status_code=201)
async def add_timeline_event(
    request_id: uuid.UUID,
    event: TimelineEventCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    req = await session.get(RecordsRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    require_department_scope(user, req.department_id)

    entry = RequestTimeline(
        request_id=request_id,
        event_type=event.event_type,
        actor_id=user.id,
        actor_role=user.role,
        description=event.description,
        internal_note=event.internal_note,
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)

    await write_audit_log(
        session=session, action="timeline_event_added", resource_type="request",
        resource_id=str(request_id), user_id=user.id,
        details={"event_type": event.event_type},
    )
    return entry


@router.get("/{request_id}/messages", response_model=list[MessageRead])
async def get_messages(
    request_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    req = await session.get(RecordsRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    require_department_scope(user, req.department_id)

    result = await session.execute(
        select(RequestMessage)
        .where(RequestMessage.request_id == request_id)
        .order_by(RequestMessage.created_at.asc())
    )
    return result.scalars().all()


@router.post("/{request_id}/messages", response_model=MessageRead, status_code=201)
async def add_message(
    request_id: uuid.UUID,
    msg: MessageCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    req = await session.get(RecordsRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    require_department_scope(user, req.department_id)

    message = RequestMessage(
        request_id=request_id,
        sender_type="staff",
        sender_id=user.id,
        message_text=msg.message_text,
        is_internal=msg.is_internal,
    )
    session.add(message)
    await session.commit()
    await session.refresh(message)

    await write_audit_log(
        session=session, action="message_added", resource_type="request",
        resource_id=str(request_id), user_id=user.id,
        details={"is_internal": msg.is_internal},
    )
    return message


@router.get("/{request_id}/fees", response_model=list[FeeLineItemRead])
async def get_fees(
    request_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    req = await session.get(RecordsRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    check_department_access(user, req.department_id)

    from app.models.fees import FeeLineItem
    result = await session.execute(
        select(FeeLineItem)
        .where(FeeLineItem.request_id == request_id)
        .order_by(FeeLineItem.created_at.asc())
    )
    return result.scalars().all()


@router.post("/{request_id}/fees", response_model=FeeLineItemRead, status_code=201)
async def add_fee(
    request_id: uuid.UUID,
    fee: FeeLineItemCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    from app.models.fees import FeeLineItem
    req = await session.get(RecordsRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    check_department_access(user, req.department_id)

    item = FeeLineItem(
        request_id=request_id,
        fee_schedule_id=fee.fee_schedule_id,
        description=fee.description,
        quantity=fee.quantity,
        unit_price=fee.unit_price,
        total=round(fee.quantity * fee.unit_price, 2),
    )
    session.add(item)

    # Update estimated total on request
    req.estimated_fee = (req.estimated_fee or 0) + item.total
    req.fee_status = "estimated"

    await session.commit()
    await session.refresh(item)

    await write_audit_log(
        session=session, action="fee_added", resource_type="request",
        resource_id=str(request_id), user_id=user.id,
        details={"description": fee.description, "total": float(item.total)},
    )
    return item


# ---------------------------------------------------------------------------
# Fee estimation & waivers
# ---------------------------------------------------------------------------


class FeeEstimateRequest(BaseModel):
    page_count: int
    fee_schedule_id: uuid.UUID


class FeeEstimateResponse(BaseModel):
    page_count: int
    unit_price: float
    total: float
    fee_type: str
    description: str


@router.post("/{request_id}/estimate-fees", response_model=FeeEstimateResponse)
async def estimate_fees(
    request_id: uuid.UUID,
    body: FeeEstimateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    """Estimate fees based on staff-entered page count and fee schedule.

    Page count is a manual staff estimate — not inferred from ingested docs.
    """
    from app.models.fees import FeeSchedule

    req = await session.get(RecordsRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    check_department_access(user, req.department_id)

    schedule = await session.get(FeeSchedule, body.fee_schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Fee schedule not found")

    total = round(body.page_count * float(schedule.amount), 2)

    return FeeEstimateResponse(
        page_count=body.page_count,
        unit_price=float(schedule.amount),
        total=total,
        fee_type=schedule.fee_type,
        description=schedule.description or f"{schedule.fee_type} @ ${schedule.amount}/unit",
    )


class FeeWaiverCreateRequest(BaseModel):
    waiver_type: str  # indigency/public_interest/media/government/other
    reason: str


class FeeWaiverReadResponse(BaseModel):
    id: uuid.UUID
    request_id: uuid.UUID
    waiver_type: str
    reason: str
    status: str
    review_notes: str | None = None
    created_at: str

    model_config = {"from_attributes": True}


class FeeWaiverReviewRequest(BaseModel):
    status: str  # approved/denied
    review_notes: str | None = None


@router.post("/{request_id}/fee-waiver", response_model=FeeWaiverReadResponse, status_code=201)
async def create_fee_waiver(
    request_id: uuid.UUID,
    body: FeeWaiverCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    """Request a fee waiver for this records request."""
    from app.models.fees import FeeWaiver

    req = await session.get(RecordsRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    check_department_access(user, req.department_id)

    if body.waiver_type not in ("indigency", "public_interest", "media", "government", "other"):
        raise HTTPException(status_code=422, detail=f"Invalid waiver_type: {body.waiver_type}")

    waiver = FeeWaiver(
        request_id=request_id,
        waiver_type=body.waiver_type,
        reason=body.reason,
        requested_by=user.id,
    )
    session.add(waiver)
    await session.commit()
    await session.refresh(waiver)

    await write_audit_log(
        session=session, action="fee_waiver_requested", resource_type="request",
        resource_id=str(request_id), user_id=user.id,
        details={"waiver_type": body.waiver_type},
    )

    return FeeWaiverReadResponse(
        id=waiver.id,
        request_id=waiver.request_id,
        waiver_type=waiver.waiver_type,
        reason=waiver.reason,
        status=waiver.status,
        review_notes=waiver.review_notes,
        created_at=waiver.created_at.isoformat(),
    )


@router.patch("/{request_id}/fee-waiver/{waiver_id}", response_model=FeeWaiverReadResponse)
async def review_fee_waiver(
    request_id: uuid.UUID,
    waiver_id: uuid.UUID,
    body: FeeWaiverReviewRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.REVIEWER)),
):
    """Approve or deny a fee waiver. Reviewer/Admin only."""
    from datetime import datetime, timezone
    from app.models.fees import FeeWaiver

    req = await session.get(RecordsRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    waiver = await session.get(FeeWaiver, waiver_id)
    if not waiver or waiver.request_id != request_id:
        raise HTTPException(status_code=404, detail="Fee waiver not found")

    if body.status not in ("approved", "denied"):
        raise HTTPException(status_code=422, detail="Status must be 'approved' or 'denied'")

    waiver.status = body.status
    waiver.review_notes = body.review_notes
    waiver.reviewed_by = user.id
    waiver.reviewed_at = datetime.now(timezone.utc)

    # If approved, update the request's fee_status
    if body.status == "approved":
        req.fee_status = "waived"

    await session.commit()
    await session.refresh(waiver)

    await write_audit_log(
        session=session, action=f"fee_waiver_{body.status}", resource_type="request",
        resource_id=str(request_id), user_id=user.id,
        details={"waiver_id": str(waiver_id), "status": body.status},
    )

    return FeeWaiverReadResponse(
        id=waiver.id,
        request_id=waiver.request_id,
        waiver_type=waiver.waiver_type,
        reason=waiver.reason,
        status=waiver.status,
        review_notes=waiver.review_notes,
        created_at=waiver.created_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# Response Letter generation
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

_LETTER_DISCLAIMER = (
    "\n\n---\n"
    "AI-GENERATED DRAFT — REQUIRES HUMAN REVIEW\n"
    "This letter was generated by CivicRecords AI and must be reviewed "
    "and approved by authorized staff before being sent to the requester."
)


def _generate_template_letter(
    req: "RecordsRequest",
    docs: list[tuple["RequestDocument", "Document"]],
) -> str:
    """Generate a template-based response letter without calling the LLM.

    Always available as a fallback when Ollama is unreachable or no model
    is loaded.
    """
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")

    lines = [
        f"Date: {today}",
        f"Re: Public Records Request — {req.requester_name}",
        f"Request ID: {req.id}",
        "",
        f"Dear {req.requester_name},",
        "",
        "Thank you for your public records request submitted to our office. "
        "Below is a summary of our response.",
        "",
        "REQUEST DESCRIPTION:",
        req.description,
        "",
    ]

    # Document listing
    included = [(rd, d) for rd, d in docs if rd.inclusion_status == InclusionStatus.INCLUDED]
    excluded = [(rd, d) for rd, d in docs if rd.inclusion_status == InclusionStatus.EXCLUDED]
    pending = [(rd, d) for rd, d in docs if rd.inclusion_status == InclusionStatus.PENDING]

    if included:
        lines.append("RESPONSIVE DOCUMENTS — INCLUDED:")
        for rd, d in included:
            name = d.display_name or d.filename
            lines.append(f"  - {name}")
        lines.append("")

    if excluded:
        lines.append("RESPONSIVE DOCUMENTS — WITHHELD / REDACTED:")
        for rd, d in excluded:
            name = d.display_name or d.filename
            exemptions = ""
            if rd.exemption_flags:
                flags = rd.exemption_flags
                exemptions = " (Exemptions: " + ", ".join(
                    f"{k}: {v}" for k, v in flags.items() if v
                ) + ")"
            lines.append(f"  - {name}{exemptions}")
        lines.append("")

    if pending:
        lines.append("DOCUMENTS UNDER REVIEW:")
        for rd, d in pending:
            name = d.display_name or d.filename
            lines.append(f"  - {name}")
        lines.append("")

    if not docs:
        lines.append("No responsive documents were identified for this request.")
        lines.append("")

    lines.extend([
        "If you have questions regarding this response, please contact our office.",
        "",
        "Sincerely,",
        "[Records Officer Name]",
        "[Municipality Name]",
    ])

    return "\n".join(lines) + _LETTER_DISCLAIMER


async def _try_llm_generation(
    req: "RecordsRequest",
    docs: list[tuple["RequestDocument", "Document"]],
) -> str | None:
    """Attempt to generate a letter via Ollama. Returns None on failure."""
    try:
        import httpx
        from app.llm.context_manager import (
            assemble_context,
            blocks_to_prompt,
            get_active_model_context_window,
        )

        # Build request context
        request_context = (
            f"Requester: {req.requester_name}\n"
            f"Request ID: {req.id}\n"
            f"Date received: {req.date_received.strftime('%Y-%m-%d')}\n"
            f"Description: {req.description}"
        )

        # Build doc summaries as chunks
        chunks = []
        for rd, d in docs:
            name = d.display_name or d.filename
            status = rd.inclusion_status.value
            exemptions = ""
            if rd.exemption_flags:
                exemptions = " | Exemptions: " + ", ".join(
                    f"{k}: {v}" for k, v in rd.exemption_flags.items() if v
                )
            chunks.append(f"Document: {name} | Status: {status}{exemptions}")

        # Exemption rules from flags
        exemption_rules = []
        for rd, d in docs:
            if rd.exemption_flags:
                for key, val in rd.exemption_flags.items():
                    if val:
                        exemption_rules.append(f"Exemption {key} applies to {d.display_name or d.filename}: {val}")

        system_prompt = (
            "You are a municipal records officer drafting a formal response letter "
            "to a public records request. Be professional, cite specific exemptions "
            "when withholding documents, and include all responsive documents. "
            "End with standard government closing language."
        )

        max_ctx = await get_active_model_context_window()

        blocks = assemble_context(
            system_prompt=system_prompt,
            request_context=request_context,
            chunks=chunks if chunks else None,
            exemption_rules=exemption_rules if exemption_rules else None,
            max_context_tokens=max_ctx,
        )
        prompt = blocks_to_prompt(blocks)

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{settings.ollama_base_url}/api/generate",
                json={
                    "model": settings.chat_model,
                    "prompt": prompt,
                    "stream": False,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                generated = data.get("response", "")
                if generated.strip():
                    return generated.strip() + _LETTER_DISCLAIMER
    except Exception as exc:
        logger.warning("LLM generation failed, falling back to template: %s", exc)

    return None


@router.post(
    "/{request_id}/response-letter",
    response_model=ResponseLetterRead,
    status_code=201,
)
async def generate_response_letter(
    request_id: uuid.UUID,
    data: ResponseLetterCreate | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    """Generate a draft response letter for a records request.

    Attempts LLM generation via Ollama first; falls back to a structured
    template if the LLM is unavailable.
    """
    req = await session.get(RecordsRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    check_department_access(user, req.department_id)

    # Fetch attached documents with their exemption flags
    result = await session.execute(
        select(RequestDocument, Document)
        .join(Document, RequestDocument.document_id == Document.id)
        .where(RequestDocument.request_id == request_id)
        .order_by(RequestDocument.attached_at)
    )
    doc_pairs = [(rd, d) for rd, d in result.all()]

    # Try LLM first, fall back to template
    content = await _try_llm_generation(req, doc_pairs)
    if content is None:
        content = _generate_template_letter(req, doc_pairs)

    letter = ResponseLetter(
        request_id=request_id,
        template_id=data.template_id if data else None,
        generated_content=content,
        status="draft",
        generated_by=user.id,
    )
    session.add(letter)

    await log_timeline(
        session, request_id, "response_drafted",
        "Response letter draft generated", user.id, user.role,
    )

    await session.commit()
    await session.refresh(letter)

    await write_audit_log(
        session=session,
        action="generate_response_letter",
        resource_type="response_letter",
        resource_id=str(letter.id),
        user_id=user.id,
        ai_generated=True,
        details={"request_id": str(request_id), "template_id": str(data.template_id) if data and data.template_id else None},
    )
    return letter


@router.get(
    "/{request_id}/response-letter",
    response_model=ResponseLetterRead,
)
async def get_response_letter(
    request_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    """Get the latest response letter for a request."""
    req = await session.get(RecordsRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    check_department_access(user, req.department_id)

    result = await session.execute(
        select(ResponseLetter)
        .where(ResponseLetter.request_id == request_id)
        .order_by(ResponseLetter.created_at.desc())
        .limit(1)
    )
    letter = result.scalar_one_or_none()
    if not letter:
        raise HTTPException(status_code=404, detail="No response letter found for this request")
    return letter


@router.patch(
    "/{request_id}/response-letter/{letter_id}",
    response_model=ResponseLetterRead,
)
async def update_response_letter(
    request_id: uuid.UUID,
    letter_id: uuid.UUID,
    data: ResponseLetterUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    """Update a response letter's edited content or status.

    Status changes to 'approved' require REVIEWER role.
    """
    letter = await session.get(ResponseLetter, letter_id)
    if not letter or letter.request_id != request_id:
        raise HTTPException(status_code=404, detail="Response letter not found")

    req = await session.get(RecordsRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    check_department_access(user, req.department_id)

    # Validate status BEFORE any mutations
    if data.status is not None:
        if data.status not in ("draft", "approved", "sent"):
            raise HTTPException(status_code=400, detail="Invalid status. Must be draft, approved, or sent")

    # Approval requires reviewer role
    if data.status == "approved":
        if user.role not in (UserRole.REVIEWER, UserRole.ADMIN):
            raise HTTPException(
                status_code=403,
                detail="Only reviewers or admins can approve response letters",
            )
        letter.approved_by = user.id
        await log_timeline(
            session, request_id, "response_approved",
            "Response letter approved", user.id, user.role,
        )

    if data.status == "sent":
        letter.sent_at = datetime.now(timezone.utc)

    if data.edited_content is not None:
        letter.edited_content = data.edited_content
    if data.status is not None:
        letter.status = data.status

    await session.commit()
    await session.refresh(letter)

    await write_audit_log(
        session=session,
        action="update_response_letter",
        resource_type="response_letter",
        resource_id=str(letter.id),
        user_id=user.id,
        details=data.model_dump(exclude_none=True),
    )
    return letter
