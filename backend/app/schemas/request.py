import uuid
from datetime import datetime
from pydantic import BaseModel, Field

from app.models.request import RequestStatus, InclusionStatus


class RequestCreate(BaseModel):
    requester_name: str
    requester_email: str | None = None
    requester_phone: str | None = None
    requester_type: str | None = None
    description: str
    statutory_deadline: datetime | None = None
    priority: str = "normal"
    department_id: uuid.UUID | None = None


class RequestRead(BaseModel):
    id: uuid.UUID
    requester_name: str
    requester_email: str | None
    requester_phone: str | None = None
    requester_type: str | None = None
    date_received: datetime
    statutory_deadline: datetime | None
    description: str
    status: RequestStatus
    assigned_to: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime
    response_draft: str | None
    review_notes: str | None
    department_id: uuid.UUID | None = None
    estimated_fee: float | None = None
    fee_status: str | None = None
    fee_waiver_requested: bool = False
    priority: str = "normal"
    closed_at: datetime | None = None
    closure_reason: str | None = None

    model_config = {"from_attributes": True}


class RequestUpdate(BaseModel):
    description: str | None = None
    status: RequestStatus | None = None
    assigned_to: uuid.UUID | None = None
    response_draft: str | None = None
    statutory_deadline: datetime | None = None


class RequestDocumentAdd(BaseModel):
    document_id: uuid.UUID
    relevance_note: str | None = None


class RequestDocumentRead(BaseModel):
    id: uuid.UUID
    request_id: uuid.UUID
    document_id: uuid.UUID
    relevance_note: str | None
    exemption_flags: dict | None
    inclusion_status: InclusionStatus
    attached_at: datetime
    attached_by: uuid.UUID

    model_config = {"from_attributes": True}


class RequestStats(BaseModel):
    total_requests: int
    by_status: dict[str, int]
    approaching_deadline: int
    overdue: int


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
