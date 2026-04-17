import uuid
from collections.abc import AsyncGenerator

import pytest
import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

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
from app.models.sync_failure import SyncFailure, SyncRunLog  # noqa: F401 — registers with Base.metadata

# Build test database URL — replace only the database name (last segment)
_base = settings.database_url.rsplit("/", 1)[0]
TEST_DATABASE_URL = f"{_base}/civicrecords_test"

# Sync URL for schema setup/teardown (avoids async concurrency issues)
_sync_url = TEST_DATABASE_URL.replace("postgresql+asyncpg", "postgresql+psycopg2")

# Async engine/session for test queries.
# NullPool ensures each session gets a fresh connection with no stale asyncpg state
# from a previous test's savepoint/rollback sequence.
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
test_session_maker = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
def setup_db():
    """Create schema via alembic upgrade head, seed admin, drop all on teardown.

    Uses a subprocess so alembic's asyncio.run() gets a fresh event loop and
    settings.database_url resolves to the test DB without touching the live DB.
    Migration 001 creates the user_role enum (create_type=True), so no pre-create needed.
    """
    import sys
    import subprocess
    from pathlib import Path

    backend_dir = str(Path(__file__).parent.parent)
    sync_engine = create_engine(_sync_url, echo=False)

    # Nuclear reset: drop and recreate the public schema so every table, type,
    # index, and alembic_version is gone — including migration-only tables like
    # _migration_015_report that are absent from Base.metadata.
    with sync_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(sa.text("DROP SCHEMA public CASCADE"))
        conn.execute(sa.text("CREATE SCHEMA public"))
        conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))

    # Run all migrations in a subprocess (avoids asyncio.run() conflicting with
    # pytest-asyncio's event loop; DATABASE_URL points at the test DB).
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env={**os.environ, "DATABASE_URL": TEST_DATABASE_URL},
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"alembic upgrade head failed:\n{result.stderr}\n{result.stdout}"
        )

    # Seed one admin user so tests using (SELECT id FROM users LIMIT 1) get a valid FK.
    with sync_engine.connect() as conn:
        conn.execute(sa.text("""
            INSERT INTO users (id, email, hashed_password, is_active, is_superuser, is_verified, role, full_name)
            VALUES (
                gen_random_uuid(),
                'seed-admin@test.internal',
                'x',
                true, true, true, 'admin', 'Seed Admin'
            )
            ON CONFLICT DO NOTHING
        """))
        conn.commit()

    yield

    # Teardown: nuclear reset so the next test starts clean.
    with sync_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(sa.text("DROP SCHEMA public CASCADE"))
        conn.execute(sa.text("CREATE SCHEMA public"))
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


@pytest.fixture
async def liaison_token_dept_a(client: AsyncClient, dept_a: uuid.UUID) -> str:
    """Liaison user in department A."""
    email = f"liaison-a-{uuid.uuid4().hex[:8]}@test.com"
    password = "liaisonpass123"
    await _create_test_user_in_dept(email, password, "Liaison A", UserRole.LIAISON, dept_a)
    login = await client.post("/auth/jwt/login", data={"username": email, "password": password})
    return login.json()["access_token"]


# ---------------------------------------------------------------------------
# Direct DB session fixtures — used by idempotency / integration tests
# ---------------------------------------------------------------------------

@pytest.fixture
async def db_session(setup_db):
    """Direct async session for integration tests that need DB access without HTTP layer."""
    async with test_session_maker() as session:
        yield session
        await session.rollback()
        await session.close()


@pytest.fixture
def db_session_factory(setup_db):
    """Returns test_session_maker for concurrency tests needing independent sessions.

    Each session created via db_session_factory() is independent — no shared transaction.
    Usage: async with db_session_factory() as s1, db_session_factory() as s2: ...
    """
    return test_session_maker
