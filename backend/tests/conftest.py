import uuid
from collections.abc import AsyncGenerator

import pytest
import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.database
from app.config import settings
from app.database import get_async_session
from app.main import create_app
from app.models.user import Base

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


@pytest.fixture
async def admin_token(client: AsyncClient) -> str:
    """Register an admin user and return JWT token."""
    reg = await client.post(
        "/auth/register",
        json={
            "email": f"admin-{uuid.uuid4().hex[:8]}@test.com",
            "password": "adminpass123",
            "full_name": "Test Admin",
            "role": "admin",
        },
    )
    email = reg.json()["email"]
    login = await client.post(
        "/auth/jwt/login",
        data={"username": email, "password": "adminpass123"},
    )
    return login.json()["access_token"]


@pytest.fixture
async def staff_token(client: AsyncClient) -> str:
    """Register a staff user and return JWT token."""
    reg = await client.post(
        "/auth/register",
        json={
            "email": f"staff-{uuid.uuid4().hex[:8]}@test.com",
            "password": "staffpass123",
            "full_name": "Test Staff",
            "role": "staff",
        },
    )
    email = reg.json()["email"]
    login = await client.post(
        "/auth/jwt/login",
        data={"username": email, "password": "staffpass123"},
    )
    return login.json()["access_token"]
