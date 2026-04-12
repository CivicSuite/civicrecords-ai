import uuid

from fastapi import Depends, HTTPException, status
from fastapi_users import FastAPIUsers

from app.auth.backend import auth_backend
from app.auth.manager import get_user_manager
from app.models.user import User, UserRole

fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])

current_active_user = fastapi_users.current_user(active=True)

# Role hierarchy: admin > reviewer > staff > read_only
ROLE_HIERARCHY = {
    UserRole.ADMIN: 4,
    UserRole.REVIEWER: 3,
    UserRole.STAFF: 2,
    UserRole.READ_ONLY: 1,
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
