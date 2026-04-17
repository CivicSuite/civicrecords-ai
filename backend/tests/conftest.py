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
    """Create and drop tables using sync engine to avoid async conflicts."""
    sync_engine = create_engine(_sync_url, echo=False)
    with sync_engine.connect() as conn:
        conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    # Ensure the user_role enum type exists with ALL current values before
    # create_all() runs.  The SQLAlchemy model uses create_type=False so
    # create_all() will not create the type itself — it must pre-exist.
    # We create the type if absent, or add missing values if it already exists.
    # NOTE: We do NOT use DROP TYPE CASCADE — that drops dependent table columns.
    _all_role_values = ('admin', 'staff', 'reviewer', 'read_only', 'liaison', 'public')
    with sync_engine.connect() as conn:
        type_exists = conn.execute(sa.text(
            "SELECT 1 FROM pg_type WHERE typname = 'user_role'"
        )).fetchone() is not None
        if not type_exists:
            conn.execute(sa.text(
                "CREATE TYPE user_role AS ENUM "
                "('admin', 'staff', 'reviewer', 'read_only', 'liaison', 'public')"
            ))
            conn.commit()
        else:
            existing = {
                row[0] for row in conn.execute(sa.text(
                    "SELECT e.enumlabel FROM pg_enum e "
                    "JOIN pg_type t ON e.enumtypid = t.oid "
                    "WHERE t.typname = 'user_role'"
                ))
            }
            conn.commit()
            for val in _all_role_values:
                if val not in existing:
                    # ADD VALUE cannot run inside a transaction block
                    with sync_engine.connect().execution_options(
                        isolation_level="AUTOCOMMIT"
                    ) as ac_conn:
                        ac_conn.execute(sa.text(
                            f"ALTER TYPE user_role ADD VALUE '{val}'"
                        ))
    # Drop all tables first to guarantee a clean schema on every test run.
    # This prevents stale columns/tables from broken previous runs.
    Base.metadata.drop_all(sync_engine)
    Base.metadata.create_all(sync_engine)
    # Add generated tsvector column (migration 004 adds this, but create_all doesn't)
    with sync_engine.connect() as conn:
        conn.execute(sa.text("""
            ALTER TABLE document_chunks
            ADD COLUMN IF NOT EXISTS content_tsvector tsvector
            GENERATED ALWAYS AS (to_tsvector('english', content_text)) STORED
        """))
        conn.commit()
    # Add migration 014 columns and partial UNIQUE indexes (create_all doesn't create these)
    with sync_engine.connect() as conn:
        conn.execute(sa.text("""
            ALTER TABLE documents
            ADD COLUMN IF NOT EXISTS connector_type VARCHAR(20),
            ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ
        """))
        conn.execute(sa.text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_indexes
                    WHERE indexname = 'uq_documents_structured_path'
                ) THEN
                    CREATE UNIQUE INDEX uq_documents_structured_path
                    ON documents (source_id, source_path)
                    WHERE connector_type IN ('rest_api', 'odbc');
                END IF;
            END$$
        """))
        conn.execute(sa.text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_indexes
                    WHERE indexname = 'uq_documents_binary_hash'
                ) THEN
                    CREATE UNIQUE INDEX uq_documents_binary_hash
                    ON documents (source_id, file_hash)
                    WHERE connector_type IS NULL OR connector_type NOT IN ('rest_api', 'odbc');
                END IF;
            END$$
        """))
        conn.execute(sa.text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'chk_source_path_length'
                ) THEN
                    ALTER TABLE documents
                    ADD CONSTRAINT chk_source_path_length
                    CHECK (source_path IS NULL OR length(source_path) <= 2048);
                END IF;
            END$$
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
