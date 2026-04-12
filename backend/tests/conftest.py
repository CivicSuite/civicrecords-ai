import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.database
from app.config import settings
from app.database import get_async_session
from app.main import create_app
from app.models.user import Base

TEST_DATABASE_URL = settings.database_url.replace("/civicrecords", "/civicrecords_test")

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session_maker = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_session_maker() as session:
        yield session


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    original_session_maker = app.database.async_session_maker
    app.database.async_session_maker = test_session_maker

    _app = create_app()
    _app.dependency_overrides[get_async_session] = override_get_session
    async with AsyncClient(
        transport=ASGITransport(app=_app), base_url="http://test"
    ) as ac:
        yield ac

    app.database.async_session_maker = original_session_maker


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
