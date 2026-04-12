from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.audit import AuditMiddleware, audit_router
from app.auth import auth_router, register_router, users_router
from app.config import settings
from app.database import engine
from app.models.user import User, UserRole
from app.schemas.user import UserCreate


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create first admin user on startup if it doesn't exist
    from sqlalchemy import select
    from app.database import async_session_maker
    from app.auth.manager import UserManager
    from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

    async with async_session_maker() as session:
        result = await session.execute(select(User).limit(1))
        if result.scalar_one_or_none() is None:
            user_db = SQLAlchemyUserDatabase(session, User)
            manager = UserManager(session=session, user_db=user_db)
            user_create = UserCreate(
                email=settings.first_admin_email,
                password=settings.first_admin_password,
                full_name="System Administrator",
                role=UserRole.ADMIN,
                is_superuser=True,
                is_active=True,
                is_verified=True,
            )
            await manager.create(user_create)
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="CivicRecords AI",
        description="AI-powered open records support for American cities",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(AuditMiddleware)

    app.include_router(auth_router, prefix="/auth/jwt", tags=["auth"])
    app.include_router(register_router, prefix="/auth", tags=["auth"])
    app.include_router(users_router, prefix="/users", tags=["users"])
    app.include_router(audit_router)

    from app.service_accounts import service_accounts_router
    app.include_router(service_accounts_router)

    from app.admin import admin_router
    app.include_router(admin_router)

    from app.datasources import datasources_router
    from app.documents import documents_router
    app.include_router(datasources_router)
    app.include_router(documents_router)

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": "0.1.0"}

    return app


app = create_app()
