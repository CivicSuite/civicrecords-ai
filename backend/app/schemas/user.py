import uuid
from datetime import datetime

from fastapi_users import schemas
from pydantic import BaseModel

from app.models.user import UserRole


class UserRead(schemas.BaseUser[uuid.UUID]):
    full_name: str
    role: UserRole
    created_at: datetime
    last_login: datetime | None


class UserCreate(schemas.BaseUserCreate):
    full_name: str = ""
    role: UserRole = UserRole.STAFF


class UserUpdate(schemas.BaseUserUpdate):
    full_name: str | None = None
    role: UserRole | None = None
