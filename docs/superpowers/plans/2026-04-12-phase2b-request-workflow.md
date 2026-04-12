# Phase 2B: Request Workflow Enhancements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add API endpoints for request timeline, messages, fees, response letters, and new request statuses. These endpoints complete the request lifecycle so a clerk can process a request end-to-end.

**Architecture:** New Pydantic schemas and router endpoints added to the existing requests module. Follow existing patterns: inline logic in routers, audit logging on every mutation, role-based auth. New status values added to the RequestStatus enum.

**Tech Stack:** FastAPI, SQLAlchemy 2.x async, Pydantic v2, Python 3.12

**Working directory:** `C:\Users\scott\Desktop\Claude\civicrecords-ai\backend`

**Key patterns (from exploration):**
- Auth: `Depends(require_role(UserRole.STAFF))` or `UserRole.REVIEWER`
- DB: `Depends(get_async_session)` → `AsyncSession`
- Audit: `await write_audit_log(session, action, resource_type, resource_id, user_id, details)`
- Schemas: `model_config = {"from_attributes": True}` for ORM reads
- Status transitions: validated via `VALID_TRANSITIONS` dict
- Existing schemas in `app/schemas/request.py`
- Existing router at `app/requests/router.py`
- Existing models at `app/models/request.py`

---

## Task 1: Extend RequestStatus Enum and Update Schemas

**Files:**
- Modify: `backend/app/models/request.py` — add new enum values
- Modify: `backend/app/schemas/request.py` — add new schemas and extend existing ones

- [ ] **Step 1: Read the current request model and schema files**

Read `backend/app/models/request.py` and `backend/app/schemas/request.py` to understand the exact current state.

- [ ] **Step 2: Add new status values to RequestStatus enum**

In `backend/app/models/request.py`, extend the `RequestStatus` enum to include:

```python
class RequestStatus(str, enum.Enum):
    RECEIVED = "received"
    CLARIFICATION_NEEDED = "clarification_needed"
    ASSIGNED = "assigned"
    SEARCHING = "searching"
    IN_REVIEW = "in_review"
    READY_FOR_RELEASE = "ready_for_release"
    DRAFTED = "drafted"
    APPROVED = "approved"
    FULFILLED = "fulfilled"
    SENT = "sent"  # legacy alias for fulfilled
    CLOSED = "closed"
```

Also update the `VALID_TRANSITIONS` dict to include new status paths.

- [ ] **Step 3: Add new Pydantic schemas**

In `backend/app/schemas/request.py`, add schemas for timeline, messages, and fees:

```python
class TimelineEventCreate(BaseModel):
    event_type: str
    description: str
    internal_note: str | None = None

class TimelineEventRead(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    request_id: uuid.UUID
    event_type: str
    actor_id: uuid.UUID | None
    actor_role: str | None
    description: str
    internal_note: str | None
    created_at: datetime

class MessageCreate(BaseModel):
    message_text: str
    is_internal: bool = False

class MessageRead(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    request_id: uuid.UUID
    sender_type: str
    sender_id: uuid.UUID | None
    message_text: str
    is_internal: bool
    created_at: datetime

class FeeLineItemCreate(BaseModel):
    description: str
    quantity: int = 1
    unit_price: float
    fee_schedule_id: uuid.UUID | None = None

class FeeLineItemRead(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    request_id: uuid.UUID
    fee_schedule_id: uuid.UUID | None
    description: str
    quantity: int
    unit_price: float
    total: float
    status: str
    created_at: datetime
```

Also update `RequestCreate` to include new optional fields:
```python
class RequestCreate(BaseModel):
    requester_name: str
    requester_email: str | None = None
    requester_phone: str | None = None
    requester_type: str | None = None
    description: str
    statutory_deadline: datetime | None = None
    priority: str = "normal"
    department_id: uuid.UUID | None = None
```

And update `RequestRead` to include the new columns.

- [ ] **Step 4: Verify imports work**

```bash
cd backend && python -c "from app.schemas.request import *; print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/request.py backend/app/schemas/request.py
git commit -m "feat: extend request status enum and add timeline/message/fee schemas"
```

---

## Task 2: Add Timeline Endpoints

**Files:**
- Modify: `backend/app/requests/router.py`

Add endpoints for request timeline events.

- [ ] **Step 1: Read the current requests router**

- [ ] **Step 2: Add timeline endpoints**

Add to the requests router:

```python
@router.get("/requests/{request_id}/timeline", response_model=list[TimelineEventRead])
async def get_timeline(
    request_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user = Depends(require_role(UserRole.STAFF)),
):
    result = await session.execute(
        select(RequestTimeline)
        .where(RequestTimeline.request_id == request_id)
        .order_by(RequestTimeline.created_at.desc())
    )
    return result.scalars().all()


@router.post("/requests/{request_id}/timeline", response_model=TimelineEventRead, status_code=201)
async def add_timeline_event(
    request_id: uuid.UUID,
    event: TimelineEventCreate,
    session: AsyncSession = Depends(get_async_session),
    user = Depends(require_role(UserRole.STAFF)),
):
    # Verify request exists
    req = await session.get(RecordsRequest, request_id)
    if not req:
        raise HTTPException(404, "Request not found")

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

    await write_audit_log(session, "timeline_event_added", "request", str(request_id), user.id,
                         {"event_type": event.event_type})
    return entry
```

Add necessary imports at the top of the router file:
```python
from app.models.request_workflow import RequestTimeline, RequestMessage, ResponseLetter
from app.schemas.request import TimelineEventCreate, TimelineEventRead, MessageCreate, MessageRead, FeeLineItemCreate, FeeLineItemRead
```

- [ ] **Step 3: Run tests**

```bash
cd backend && DATABASE_URL=postgresql+asyncpg://civicrecords:civicrecords@localhost:5432/civicrecords python -m pytest tests/ -q
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/requests/router.py
git commit -m "feat: add request timeline GET/POST endpoints"
```

---

## Task 3: Add Message Endpoints

**Files:**
- Modify: `backend/app/requests/router.py`

- [ ] **Step 1: Add message endpoints**

```python
@router.get("/requests/{request_id}/messages", response_model=list[MessageRead])
async def get_messages(
    request_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user = Depends(require_role(UserRole.STAFF)),
):
    result = await session.execute(
        select(RequestMessage)
        .where(RequestMessage.request_id == request_id)
        .order_by(RequestMessage.created_at.asc())
    )
    return result.scalars().all()


@router.post("/requests/{request_id}/messages", response_model=MessageRead, status_code=201)
async def add_message(
    request_id: uuid.UUID,
    msg: MessageCreate,
    session: AsyncSession = Depends(get_async_session),
    user = Depends(require_role(UserRole.STAFF)),
):
    req = await session.get(RecordsRequest, request_id)
    if not req:
        raise HTTPException(404, "Request not found")

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

    await write_audit_log(session, "message_added", "request", str(request_id), user.id,
                         {"is_internal": msg.is_internal})
    return message
```

- [ ] **Step 2: Run tests and commit**

```bash
cd backend && DATABASE_URL=postgresql+asyncpg://civicrecords:civicrecords@localhost:5432/civicrecords python -m pytest tests/ -q
git add backend/app/requests/router.py
git commit -m "feat: add request messages GET/POST endpoints"
```

---

## Task 4: Add Fee Endpoints

**Files:**
- Modify: `backend/app/requests/router.py`

- [ ] **Step 1: Add fee endpoints**

```python
@router.get("/requests/{request_id}/fees", response_model=list[FeeLineItemRead])
async def get_fees(
    request_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user = Depends(require_role(UserRole.STAFF)),
):
    from app.models.fees import FeeLineItem
    result = await session.execute(
        select(FeeLineItem)
        .where(FeeLineItem.request_id == request_id)
        .order_by(FeeLineItem.created_at.asc())
    )
    return result.scalars().all()


@router.post("/requests/{request_id}/fees", response_model=FeeLineItemRead, status_code=201)
async def add_fee(
    request_id: uuid.UUID,
    fee: FeeLineItemCreate,
    session: AsyncSession = Depends(get_async_session),
    user = Depends(require_role(UserRole.STAFF)),
):
    from app.models.fees import FeeLineItem
    req = await session.get(RecordsRequest, request_id)
    if not req:
        raise HTTPException(404, "Request not found")

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

    await write_audit_log(session, "fee_added", "request", str(request_id), user.id,
                         {"description": fee.description, "total": float(item.total)})
    return item
```

- [ ] **Step 2: Run tests and commit**

```bash
cd backend && DATABASE_URL=postgresql+asyncpg://civicrecords:civicrecords@localhost:5432/civicrecords python -m pytest tests/ -q
git add backend/app/requests/router.py
git commit -m "feat: add request fee line items GET/POST endpoints"
```

---

## Task 5: Add Automated Timeline Logging to Status Transitions

**Files:**
- Modify: `backend/app/requests/router.py`

Every status transition should automatically create a timeline entry. Modify the existing `update_request`, `submit_for_review`, `approve_request`, and `reject_request` endpoints.

- [ ] **Step 1: Create a helper function for timeline logging**

Add near the top of the router:

```python
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
```

- [ ] **Step 2: Add timeline logging calls to existing status-change endpoints**

In `update_request` (where status changes happen):
```python
if data.status and data.status != req.status:
    await log_timeline(session, request_id, "status_change",
                      f"Status changed to {data.status.value}", user.id, user.role)
```

In `submit_for_review`:
```python
await log_timeline(session, request_id, "status_change",
                  "Submitted for review", user.id, user.role)
```

In `approve_request`:
```python
await log_timeline(session, request_id, "response_approved",
                  "Request approved", user.id, user.role)
```

In `reject_request`:
```python
await log_timeline(session, request_id, "status_change",
                  "Request rejected — returned for revision", user.id, user.role)
```

- [ ] **Step 3: Run tests and commit**

```bash
cd backend && DATABASE_URL=postgresql+asyncpg://civicrecords:civicrecords@localhost:5432/civicrecords python -m pytest tests/ -q
git add backend/app/requests/router.py
git commit -m "feat: auto-log timeline entries on status transitions"
```

---

## Summary

After Phase 2B, the request workflow has:
- 6 new endpoints: timeline (GET/POST), messages (GET/POST), fees (GET/POST)
- Extended status enum: 11 states (received through closed)
- Automatic timeline logging on every status change
- Updated RequestCreate/RequestRead schemas with new fields
- All audit-logged, role-authenticated
