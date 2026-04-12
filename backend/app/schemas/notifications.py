import uuid
from datetime import datetime

from pydantic import BaseModel


class NotificationTemplateCreate(BaseModel):
    event_type: str
    channel: str = "email"
    subject_template: str
    body_template: str


class NotificationTemplateRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    event_type: str
    channel: str
    subject_template: str
    body_template: str
    is_active: bool
    created_at: datetime


class NotificationTemplateUpdate(BaseModel):
    subject_template: str | None = None
    body_template: str | None = None
    is_active: bool | None = None


class NotificationLogRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    template_id: uuid.UUID | None
    recipient_email: str
    request_id: uuid.UUID | None
    channel: str
    status: str
    sent_at: datetime | None
    error_message: str | None
    created_at: datetime
