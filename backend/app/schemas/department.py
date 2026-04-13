import uuid
from datetime import datetime
from pydantic import BaseModel


class DepartmentCreate(BaseModel):
    name: str
    code: str
    contact_email: str | None = None


class DepartmentRead(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    contact_email: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


class DepartmentUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    contact_email: str | None = None
