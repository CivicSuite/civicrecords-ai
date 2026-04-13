import uuid
from datetime import datetime

from fastapi_users import schemas
from pydantic import BaseModel, model_validator

from app.models.user import UserRole


class UserRead(schemas.BaseUser[uuid.UUID]):
    full_name: str
    role: UserRole
    created_at: datetime
    last_login: datetime | None


class UserCreate(schemas.BaseUserCreate):
    full_name: str = ""
    role: UserRole = UserRole.STAFF

    @model_validator(mode="after")
    def force_staff_role(self):
        """Prevent callers from escalating role. Admin user creation goes through /admin/users."""
        self.role = UserRole.STAFF
        return self


class AdminUserCreate(schemas.BaseUserCreate):
    """Schema for admin-only user creation endpoint. Role IS caller-supplied."""
    full_name: str = ""
    role: UserRole = UserRole.STAFF


class UserUpdate(schemas.BaseUserUpdate):
    full_name: str | None = None
    role: UserRole | None = None
