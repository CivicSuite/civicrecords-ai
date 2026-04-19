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
    department_id: uuid.UUID | None = None


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
    department_id: uuid.UUID | None = None


class UserUpdate(schemas.BaseUserUpdate):
    full_name: str | None = None
    role: UserRole | None = None


class UserSelfUpdate(schemas.BaseUserUpdate):
    """Schema for user self-update via PATCH /users/me.

    Excludes role and department_id. Any payload containing those fields is
    rejected at parse time (HTTP 422). Role and department changes require
    admin privileges via /admin/users/{id}.
    """
    full_name: str | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_privileged_fields(cls, values):
        if isinstance(values, dict):
            forbidden = {"role", "department_id"} & set(values.keys())
            if forbidden:
                raise ValueError(
                    f"Fields cannot be set via self-update: {sorted(forbidden)}. "
                    "Role and department changes require admin."
                )
        return values
