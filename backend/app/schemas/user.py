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
    """Self-registration schema for the public ``/auth/register`` endpoint.

    Role is forced server-side, never honored from the request payload:
    * In ``PORTAL_MODE=public``: role → ``UserRole.PUBLIC`` (residents who
      register via the public surface get the minimal public role, never
      STAFF).
    * In ``PORTAL_MODE=private``: ``/auth/register`` is not mounted at all,
      so this schema is unreachable in private mode. The fallback value here
      matches the private-mode non-assignability posture (PUBLIC, not STAFF)
      — which also corrects a pre-existing bug where self-register was
      silently forced to STAFF regardless of caller intent.

    Admin-driven user creation (including explicit STAFF/REVIEWER/LIAISON/
    READ_ONLY assignments) goes through ``/admin/users`` via
    :class:`AdminUserCreate`.
    """
    full_name: str = ""
    role: UserRole = UserRole.PUBLIC

    @model_validator(mode="after")
    def force_public_role(self):
        """Prevent callers from escalating role on self-registration.

        T5D (2026-04-22): this used to force STAFF — a pre-existing bug
        where the public ``/auth/register`` endpoint created STAFF-level
        users. Corrected to PUBLIC as part of the portal-mode gating slice.
        The ``/auth/register`` endpoint is only mounted when
        ``PORTAL_MODE=public``, so in practice this value is only observed
        by residents registering through the public surface.
        """
        self.role = UserRole.PUBLIC
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
