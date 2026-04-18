import asyncio
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

# Per-test async engine and session maker — populated by the client fixture.
# Creating the engine at module level ties it to the import-time event loop
# (which doesn't exist yet), causing "Future attached to a different loop" errors
# when pytest-asyncio creates per-function event loops.  These are set fresh
# for each test inside client() so asyncpg internals are always loop-correct.
_test_engine = None
_test_session_maker = None


class _SessionProxy:
    """Callable that delegates to the per-test session maker set by the client fixture.

    Implemented as a class instance rather than a function so that pytest does not
    collect it as a test when test files do 'from tests.conftest import test_session_maker'.
    """
    def __call__(self):
        return _test_session_maker()


# Imported by test_deadline_notifications, test_smtp_delivery, test_audit, etc.
test_session_maker = _SessionProxy()


def get_test_session():
    """Alias for test_session_maker — usable without the conftest collection concern."""
    return _test_session_maker()


@pytest.fixture
def setup_db():
    """Drop and recreate civicrecords_test, install vector, run migrations, seed admin.

    Drops and recreates the entire test database each time so the vector extension
    and all catalog state are always clean. DROP SCHEMA CASCADE orphans the
    pg_extension namespace OID, making subsequent CREATE EXTENSION a no-op while
    the actual type is gone — full DB recreation is the only reliable fix.
    Uses a subprocess for alembic so asyncio.run() gets a fresh event loop and
    DATABASE_URL resolves to the test DB without touching the live DB.
    """
    import sys
    import subprocess
    from pathlib import Path

    backend_dir = str(Path(__file__).parent.parent)

    # Connect to the live database to drop and recreate the test database.
    # This guarantees a clean catalog — no dangling extension OIDs, no stale types.
    _main_sync_url = _sync_url.rsplit("/", 1)[0] + "/civicrecords"
    main_engine = create_engine(_main_sync_url, echo=False)
    with main_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        # WITH (FORCE) atomically terminates all connections before dropping —
        # avoids the race condition between pg_terminate_backend and DROP DATABASE
        # (requires PostgreSQL 13+; the project targets PostgreSQL 17).
        conn.execute(sa.text("DROP DATABASE IF EXISTS civicrecords_test WITH (FORCE)"))
        conn.execute(sa.text("CREATE DATABASE civicrecords_test"))
    main_engine.dispose()

    sync_engine = create_engine(_sync_url, echo=False)
    with sync_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
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

    # Teardown: close the sync engine; next test's setup_db will drop/recreate the DB.
    sync_engine.dispose()


async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
    async with _test_session_maker() as session:
        yield session


@pytest.fixture
async def client(setup_db) -> AsyncGenerator[AsyncClient, None]:
    global _test_engine, _test_session_maker
    # Create a fresh engine per test so asyncpg internals are tied to this
    # test's event loop — prevents "Future attached to a different loop" errors.
    _test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
    _test_session_maker = async_sessionmaker(_test_engine, class_=AsyncSession, expire_on_commit=False)

    original_session_maker = app.database.async_session_maker
    app.database.async_session_maker = _test_session_maker

    _app = create_app()
    _app.dependency_overrides[get_async_session] = override_get_session
    async with AsyncClient(
        transport=ASGITransport(app=_app), base_url="http://test"
    ) as ac:
        yield ac

    app.database.async_session_maker = original_session_maker
    await _test_engine.dispose()
    # Flush asyncpg's pending cancel/close callbacks so PostgreSQL can immediately
    # reclaim the connection slots.  Without this, GC-triggered Connection._cancel()
    # coroutines run after the event loop closes, leaving connections open in
    # PostgreSQL until TCP timeout — causing "too many clients" after many tests.
    await asyncio.sleep(0.05)
    import gc
    gc.collect()  # force-collect any unreferenced asyncpg Connection objects now
    await asyncio.sleep(0)  # second pass to process newly scheduled cancel callbacks
    _test_engine = None
    _test_session_maker = None


async def _create_test_user(email: str, password: str, full_name: str, role: UserRole) -> None:
    """Create a user directly via UserManager (no HTTP endpoint needed)."""
    from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
    from app.auth.manager import UserManager
    from app.schemas.user import AdminUserCreate

    async with _test_session_maker() as session:
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
    async with _test_session_maker() as session:
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

    async with _test_session_maker() as session:
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
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    session = session_maker()
    try:
        yield session
    finally:
        # Don't rollback — the database is dropped and recreated per test via setup_db.
        # Attempting rollback in the pytest-asyncio finalizer runs on a NEW event loop,
        # causing "Future attached to a different loop" on the asyncpg connection.
        await engine.dispose()
        import gc
        gc.collect()


@pytest.fixture
def db_session_factory(setup_db):
    """Returns a per-test session_maker for concurrency tests needing independent sessions.

    Each session created via db_session_factory() is independent — no shared transaction.
    Usage: async with db_session_factory() as s1, db_session_factory() as s2: ...
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
