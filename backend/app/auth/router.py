from app.auth.backend import auth_backend
from app.auth.dependencies import fastapi_users
from app.schemas.user import UserCreate, UserRead, UserSelfUpdate

auth_router = fastapi_users.get_auth_router(auth_backend)

# T5D — self-registration router. `register_router` is always constructed
# here, but whether it gets **mounted** on the live FastAPI app is decided
# dynamically in ``app.main.create_app()`` based on ``settings.portal_mode``.
# Keeping the gate at `create_app` time (instead of module-import time)
# lets per-test fixtures flip ``settings.portal_mode`` and get a cleanly
# regated app without reimporting modules. In ``PORTAL_MODE=private`` this
# router is not mounted, so ``POST /auth/register`` returns the
# FastAPI 404 — the endpoint effectively does not exist on the public wire
# (403 would advertise that registration is a gated feature; 404 does not).
register_router = fastapi_users.get_register_router(UserRead, UserCreate)

# PATCH /users/me uses UserSelfUpdate so role and department_id cannot be
# self-modified. Admin role/department changes go through /admin/users/{id}.
users_router = fastapi_users.get_users_router(UserRead, UserSelfUpdate)
