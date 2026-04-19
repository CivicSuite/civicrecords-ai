from app.auth.backend import auth_backend
from app.auth.dependencies import fastapi_users
from app.schemas.user import UserCreate, UserRead, UserSelfUpdate

auth_router = fastapi_users.get_auth_router(auth_backend)
register_router = fastapi_users.get_register_router(UserRead, UserCreate)
# PATCH /users/me uses UserSelfUpdate so role and department_id cannot be
# self-modified. Admin role/department changes go through /admin/users/{id}.
users_router = fastapi_users.get_users_router(UserRead, UserSelfUpdate)
