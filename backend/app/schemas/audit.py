import uuid
from datetime import datetime

from pydantic import BaseModel


class AuditLogRead(BaseModel):
    id: int
    prev_hash: str
    entry_hash: str
    timestamp: datetime
    user_id: uuid.UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    details: dict | None
    ai_generated: bool

    model_config = {"from_attributes": True}


class AuditLogQuery(BaseModel):
    action: str | None = None
    resource_type: str | None = None
    user_id: uuid.UUID | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    limit: int = 100
    offset: int = 0


class AuditChainVerification(BaseModel):
    is_valid: bool
    entries_checked: int
    error_message: str
