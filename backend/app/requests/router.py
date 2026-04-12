import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.logger import write_audit_log
from app.auth.dependencies import require_role
from app.database import get_async_session
from app.models.document import Document
from app.models.request import (
    DocumentCache, InclusionStatus, RecordsRequest, RequestDocument, RequestStatus,
)
from app.models.user import User, UserRole
from app.schemas.request import (
    RequestCreate, RequestDocumentAdd, RequestDocumentRead,
    RequestRead, RequestStats, RequestUpdate,
)

router = APIRouter(prefix="/requests", tags=["requests"])

# Valid status transitions
VALID_TRANSITIONS = {
    RequestStatus.RECEIVED: {RequestStatus.SEARCHING},
    RequestStatus.SEARCHING: {RequestStatus.IN_REVIEW, RequestStatus.DRAFTED},
    RequestStatus.IN_REVIEW: {RequestStatus.DRAFTED},
    RequestStatus.DRAFTED: {RequestStatus.IN_REVIEW, RequestStatus.APPROVED},
    RequestStatus.APPROVED: {RequestStatus.SENT},
}


@router.post("/", response_model=RequestRead, status_code=201)
async def create_request(
    data: RequestCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    req = RecordsRequest(
        requester_name=data.requester_name,
        requester_email=data.requester_email,
        description=data.description,
        statutory_deadline=data.statutory_deadline,
        created_by=user.id,
        assigned_to=user.id,
    )
    session.add(req)
    await session.commit()
    await session.refresh(req)

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
    user: User = Depends(require_role(UserRole.STAFF)),
):
    stmt = select(RecordsRequest).order_by(RecordsRequest.created_at.desc())
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
    user: User = Depends(require_role(UserRole.STAFF)),
):
    total = (await session.execute(select(func.count(RecordsRequest.id)))).scalar() or 0

    by_status = {}
    for s in RequestStatus:
        count = (await session.execute(
            select(func.count(RecordsRequest.id)).where(RecordsRequest.status == s)
        )).scalar() or 0
        by_status[s.value] = count

    now = datetime.now(timezone.utc)
    three_days = now + timedelta(days=3)

    approaching = (await session.execute(
        select(func.count(RecordsRequest.id)).where(
            RecordsRequest.statutory_deadline.isnot(None),
            RecordsRequest.statutory_deadline <= three_days,
            RecordsRequest.statutory_deadline > now,
            RecordsRequest.status.notin_([RequestStatus.SENT, RequestStatus.APPROVED]),
        )
    )).scalar() or 0

    overdue = (await session.execute(
        select(func.count(RecordsRequest.id)).where(
            RecordsRequest.statutory_deadline.isnot(None),
            RecordsRequest.statutory_deadline < now,
            RecordsRequest.status.notin_([RequestStatus.SENT, RequestStatus.APPROVED]),
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
    user: User = Depends(require_role(UserRole.STAFF)),
):
    req = await session.get(RecordsRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
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

    if data.status is not None and data.status != req.status:
        valid = VALID_TRANSITIONS.get(req.status, set())
        if data.status not in valid:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot transition from {req.status.value} to {data.status.value}",
            )
        req.status = data.status

    if data.description is not None:
        req.description = data.description
    if data.assigned_to is not None:
        req.assigned_to = data.assigned_to
    if data.response_draft is not None:
        req.response_draft = data.response_draft
    if data.statutory_deadline is not None:
        req.statutory_deadline = data.statutory_deadline

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
        import shutil
        from pathlib import Path

        cache_dir = Path("/data/cache") / str(request_id)
        cache_dir.mkdir(parents=True, exist_ok=True)
        source = Path(doc.source_path)
        if source.exists():
            dest = cache_dir / source.name
            shutil.copy2(str(source), str(dest))
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
    user: User = Depends(require_role(UserRole.STAFF)),
):
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

    if req.status not in (RequestStatus.SEARCHING, RequestStatus.DRAFTED):
        raise HTTPException(status_code=400, detail=f"Cannot submit for review from status {req.status.value}")

    req.status = RequestStatus.IN_REVIEW
    await session.commit()
    await session.refresh(req)

    await write_audit_log(
        session=session, action="submit_for_review", resource_type="request",
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

    if req.status != RequestStatus.DRAFTED:
        raise HTTPException(status_code=400, detail=f"Can only approve from 'drafted' status, current: {req.status.value}")

    req.status = RequestStatus.APPROVED
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

    if req.status != RequestStatus.IN_REVIEW:
        raise HTTPException(status_code=400, detail="Can only reject from 'in_review' status")

    req.status = RequestStatus.DRAFTED
    req.review_notes = reason if reason else None
    await session.commit()
    await session.refresh(req)

    await write_audit_log(
        session=session, action="reject_request", resource_type="request",
        resource_id=str(request_id), user_id=user.id,
        details={"reason": reason},
    )
    return req
