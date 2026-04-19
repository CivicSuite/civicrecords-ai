import uuid

from fastapi import Depends, HTTPException, status
from fastapi_users import FastAPIUsers

from app.auth.backend import auth_backend
from app.auth.manager import get_user_manager
from app.models.user import User, UserRole

fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])

current_active_user = fastapi_users.current_user(active=True)

# Role hierarchy: admin > reviewer > staff > liaison > read_only > public
ROLE_HIERARCHY = {
    UserRole.ADMIN: 6,
    UserRole.REVIEWER: 5,
    UserRole.STAFF: 4,
    UserRole.LIAISON: 3,
    UserRole.READ_ONLY: 2,
    UserRole.PUBLIC: 1,
}


def require_role(minimum_role: UserRole):
    """Dependency that enforces a minimum role level."""

    async def _check_role(user: User = Depends(current_active_user)) -> User:
        if ROLE_HIERARCHY.get(user.role, 0) < ROLE_HIERARCHY[minimum_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {minimum_role.value} role or higher",
            )
        return user

    return _check_role


def check_department_access(user: User, resource_department_id: uuid.UUID | None) -> None:
    """Raise 403 if non-admin user tries to access resource in another department.

    Call this in endpoint logic after loading the resource.
    Shared resources (department_id=None) are accessible to everyone.

    NOTE: this helper is fail-open on ``resource_department_id is None``. New code
    should prefer :func:`require_department_scope` which is fail-closed.
    Migration of existing callers (requests, search, analytics routers) is
    tracked as a follow-up to Tier 2A.
    """
    if user.role == UserRole.ADMIN:
        return
    if resource_department_id is None:
        return  # shared resource
    if user.department_id != resource_department_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: resource belongs to another department",
        )


def require_department_scope(user: User, resource_department_id: uuid.UUID | None) -> None:
    """Fail-closed department access check. Raises HTTP 403 on deny.

    Rules:
    - Admin: always allowed.
    - Non-admin with ``user.department_id is None``: denied.
    - Non-admin with ``resource_department_id is None``: denied (no shared-resource shortcut).
    - Non-admin otherwise: allowed iff ``user.department_id == resource_department_id``.

    Call this after loading the resource. For list endpoints, apply the
    equivalent ``WHERE`` clause on the query instead::

        if user.role != UserRole.ADMIN:
            if user.department_id is None:
                raise HTTPException(403, ...)
            stmt = stmt.where(Model.department_id == user.department_id)
    """
    if user.role == UserRole.ADMIN:
        return
    if user.department_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: user is not assigned to a department",
        )
    if resource_department_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: resource has no department scope",
        )
    if user.department_id != resource_department_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: resource belongs to another department",
        )
