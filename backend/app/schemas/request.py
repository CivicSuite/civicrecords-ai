import uuid
from datetime import datetime
from pydantic import BaseModel, Field

from app.models.request import RequestStatus, InclusionStatus


class RequestCreate(BaseModel):
    requester_name: str
    requester_email: str | None = None
    description: str
    statutory_deadline: datetime | None = None


class RequestRead(BaseModel):
    id: uuid.UUID
    requester_name: str
    requester_email: str | None
    date_received: datetime
    statutory_deadline: datetime | None
    description: str
    status: RequestStatus
    assigned_to: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime
    response_draft: str | None
    review_notes: str | None

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
