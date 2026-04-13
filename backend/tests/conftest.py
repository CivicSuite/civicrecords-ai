import uuid
from collections.abc import AsyncGenerator

import pytest
import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import os
# Set a proper-length JWT secret before importing settings to suppress warnings
os.environ.setdefault("JWT_SECRET", "a" * 64)
os.environ["TESTING"] = "1"

import app.database
from app.config import settings
from app.database import get_async_session
from app.main import create_app
from app.models.user import Base, User, UserRole
from app.models.departments import Department

# Build test database URL — replace only the database name (last segment)
_base = settings.database_url.rsplit("/", 1)[0]
TEST_DATABASE_URL = f"{_base}/civicrecords_test"

# Sync URL for schema setup/teardown (avoids async concurrency issues)
_sync_url = TEST_DATABASE_URL.replace("postgresql+asyncpg", "postgresql+psycopg2")

# Async engine/session for test queries
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session_maker = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
def setup_db():
    """Create and drop tables using sync engine to avoid async conflicts."""
    sync_engine = create_engine(_sync_url, echo=False)
    with sync_engine.connect() as conn:
        conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(sync_engine)
    # Add generated tsvector column (migration 004 adds this, but create_all doesn't)
    with sync_engine.connect() as conn:
        conn.execute(sa.text("""
            ALTER TABLE document_chunks
            ADD COLUMN IF NOT EXISTS content_tsvector tsvector
            GENERATED ALWAYS AS (to_tsvector('english', content_text)) STORED
        """))
        conn.commit()
    yield
    Base.metadata.drop_all(sync_engine)
    sync_engine.dispose()


async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_session_maker() as session:
        yield session


@pytest.fixture
async def client(setup_db) -> AsyncGenerator[AsyncClient, None]:
    original_session_maker = app.database.async_session_maker
    app.database.async_session_maker = test_session_maker

    _app = create_app()
    _app.dependency_overrides[get_async_session] = override_get_session
    async with AsyncClient(
        transport=ASGITransport(app=_app), base_url="http://test"
    ) as ac:
        yield ac

    app.database.async_session_maker = original_session_maker
    await test_engine.dispose()


async def _create_test_user(email: str, password: str, full_name: str, role: UserRole) -> None:
    """Create a user directly via UserManager (no HTTP endpoint needed)."""
    from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
    from app.auth.manager import UserManager
    from app.schemas.user import AdminUserCreate

    async with test_session_maker() as session:
        user_db = SQLAlchemyUserDatabase(session, User)
        manager = UserManager(session=session, user_db=user_db)
        user_create = AdminUserCreate(
            email=email,
            password=password,
            full_name=full_name,
            role=role,
            is_active=True,
            is_verified=True,
            is_superuser=(role == UserRole.ADMIN),
        )
        await manager.create(user_create)


@pytest.fixture
async def admin_token(client: AsyncClient) -> str:
    """Create an admin user directly and return JWT token."""
    email = f"admin-{uuid.uuid4().hex[:8]}@test.com"
    password = "adminpass123"
    await _create_test_user(email, password, "Test Admin", UserRole.ADMIN)
    login = await client.post(
        "/auth/jwt/login",
        data={"username": email, "password": password},
    )
    return login.json()["access_token"]


@pytest.fixture
async def staff_token(client: AsyncClient) -> str:
    """Create a staff user directly and return JWT token."""
    email = f"staff-{uuid.uuid4().hex[:8]}@test.com"
    password = "staffpass123"
    await _create_test_user(email, password, "Test Staff", UserRole.STAFF)
    login = await client.post(
        "/auth/jwt/login",
        data={"username": email, "password": password},
    )
    return login.json()["access_token"]


# ---------------------------------------------------------------------------
# Department-aware helpers and fixtures (Phase 2)
# ---------------------------------------------------------------------------

async def _create_department(name: str, code: str) -> uuid.UUID:
    """Create a department directly in test DB, return its ID."""
    async with test_session_maker() as session:
        dept = Department(name=name, code=code)
        session.add(dept)
        await session.commit()
        await session.refresh(dept)
        return dept.id


async def _create_test_user_in_dept(
    email: str, password: str, full_name: str, role: UserRole, department_id: uuid.UUID
) -> None:
    """Create a user with a department assignment."""
    from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
    from app.auth.manager import UserManager
    from app.schemas.user import AdminUserCreate

    async with test_session_maker() as session:
        user_db = SQLAlchemyUserDatabase(session, User)
        manager = UserManager(session=session, user_db=user_db)
        user_create = AdminUserCreate(
            email=email,
            password=password,
            full_name=full_name,
            role=role,
            department_id=department_id,
            is_active=True,
            is_verified=True,
            is_superuser=False,
        )
        await manager.create(user_create)


@pytest.fixture
async def dept_a(client: AsyncClient) -> uuid.UUID:
    """Create department A for testing."""
    return await _create_department("Police Department", "PD")


@pytest.fixture
async def dept_b(client: AsyncClient) -> uuid.UUID:
    """Create department B for testing."""
    return await _create_department("Finance Department", "FIN")


@pytest.fixture
async def staff_token_dept_a(client: AsyncClient, dept_a: uuid.UUID) -> str:
    """Staff user in department A."""
    email = f"staff-a-{uuid.uuid4().hex[:8]}@test.com"
    password = "staffpass123"
    await _create_test_user_in_dept(email, password, "Staff A", UserRole.STAFF, dept_a)
    login = await client.post("/auth/jwt/login", data={"username": email, "password": password})
    return login.json()["access_token"]


@pytest.fixture
async def staff_token_dept_b(client: AsyncClient, dept_b: uuid.UUID) -> str:
    """Staff user in department B."""
    email = f"staff-b-{uuid.uuid4().hex[:8]}@test.com"
    password = "staffpass123"
    await _create_test_user_in_dept(email, password, "Staff B", UserRole.STAFF, dept_b)
    login = await client.post("/auth/jwt/login", data={"username": email, "password": password})
    return login.json()["access_token"]


@pytest.fixture
async def reviewer_token_dept_a(client: AsyncClient, dept_a: uuid.UUID) -> str:
    """Reviewer user in department A."""
    email = f"reviewer-a-{uuid.uuid4().hex[:8]}@test.com"
    password = "reviewerpass123"
    await _create_test_user_in_dept(email, password, "Reviewer A", UserRole.REVIEWER, dept_a)
    login = await client.post("/auth/jwt/login", data={"username": email, "password": password})
    return login.json()["access_token"]
