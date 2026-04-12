import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.user import UserRole


class ServiceAccountCreate(BaseModel):
    name: str
    role: UserRole = UserRole.READ_ONLY


class ServiceAccountRead(BaseModel):
    id: uuid.UUID
    name: str
    role: UserRole
    created_by: uuid.UUID
    created_at: datetime
    is_active: bool

    model_config = {"from_attributes": True}


class ServiceAccountCreated(ServiceAccountRead):
    """Returned only on creation — includes the plaintext API key (shown once)."""
    api_key: str


class ServiceAccountUpdate(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None
