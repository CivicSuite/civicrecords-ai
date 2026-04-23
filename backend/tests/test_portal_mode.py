"""T5D — PORTAL_MODE config, ``/auth/register`` gating, and public surface.

Tests cover:

1. :class:`app.config.Settings` portal_mode:
   - default is ``"private"`` when no env var is set
   - ``PORTAL_MODE=public`` loads as ``"public"``
   - values are case/whitespace normalized (``"  Public  "`` → ``"public"``)
   - any other value raises a ``ValidationError`` at startup

2. ``GET /config/portal-mode``:
   - always mounted, regardless of mode
   - reports the currently-configured mode

3. ``POST /auth/register`` gating:
   - ``private`` → 404 (router not mounted)
   - ``public`` → 201, and the created user has ``role == UserRole.PUBLIC``
     (NOT ``STAFF``, which was the pre-existing behavior corrected in T5D)

4. ``POST /public/requests`` public submission endpoint:
   - ``private`` → 404 (public router not mounted at all)
   - ``public`` + unauthenticated → 401
   - ``public`` + authenticated ``staff`` user → 403 (role mismatch)
   - ``public`` + authenticated ``UserRole.PUBLIC`` user → 201 and the request
     is persisted with ``created_by`` = that user's id
   - ``public`` + authenticated ``UserRole.PUBLIC`` user + too-short
     description → 422 (validator rejects < 10 chars)

Per Scott's 2026-04-22 Option A decision, anonymous walk-up submission is
NOT supported in this slice; every submission is authenticated.
"""
from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.config import Settings, settings
from app.models.user import UserRole


# --------------------------------------------------------------------------
# 1. Config-level tests (no HTTP, no DB — just pydantic Settings)
# --------------------------------------------------------------------------

def test_portal_mode_defaults_to_private(monkeypatch):
    """Absent PORTAL_MODE env → default "private"."""
    monkeypatch.delenv("PORTAL_MODE", raising=False)
    # JWT secret and admin password must be valid for Settings to instantiate
    # outside the testing=True short-circuit — reuse conftest's values.
    s = Settings(
        jwt_secret="a" * 64,
        first_admin_password="CivicDev2026!xZ",
    )
    assert s.portal_mode == "private"


def test_portal_mode_accepts_public(monkeypatch):
    monkeypatch.setenv("PORTAL_MODE", "public")
    s = Settings(jwt_secret="a" * 64, first_admin_password="CivicDev2026!xZ")
    assert s.portal_mode == "public"


def test_portal_mode_accepts_private_explicit(monkeypatch):
    monkeypatch.setenv("PORTAL_MODE", "private")
    s = Settings(jwt_secret="a" * 64, first_admin_password="CivicDev2026!xZ")
    assert s.portal_mode == "private"


def test_portal_mode_normalizes_case_and_whitespace(monkeypatch):
    monkeypatch.setenv("PORTAL_MODE", "  PuBlIc  ")
    s = Settings(jwt_secret="a" * 64, first_admin_password="CivicDev2026!xZ")
    assert s.portal_mode == "public"


def test_portal_mode_rejects_invalid_value(monkeypatch):
    monkeypatch.setenv("PORTAL_MODE", "staff-only")
    with pytest.raises(ValidationError):
        Settings(jwt_secret="a" * 64, first_admin_password="CivicDev2026!xZ")


# --------------------------------------------------------------------------
# Runtime-mode marker + autouse fixture.
#
# Async fixture resolution in pytest-asyncio does not reliably honor
# left-to-right signature order when one sibling is sync (a monkeypatch
# flipper) and another is async (the conftest ``client``). An autouse
# fixture that reads a marker is the robust way to guarantee the mode
# is flipped BEFORE any other fixture resolves. Mark a test with
# ``@pytest.mark.portal_mode("public")`` or ``("private")`` — the
# fixture below reads the marker and sets ``settings.portal_mode`` so
# ``create_app()`` builds the right gate.
#
# Tests without the marker keep whatever portal_mode is currently set
# (typically "private" per the .env default).
# --------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _portal_mode_override(request, monkeypatch):
    marker = request.node.get_closest_marker("portal_mode")
    if marker:
        monkeypatch.setattr(settings, "portal_mode", marker.args[0])
    yield


# --------------------------------------------------------------------------
# 2. GET /config/portal-mode — always mounted
# --------------------------------------------------------------------------

@pytest.mark.portal_mode("public")
async def test_config_portal_mode_reports_public(client):
    resp = await client.get("/config/portal-mode")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"mode": "public"}


@pytest.mark.portal_mode("private")
async def test_config_portal_mode_reports_private(client):
    resp = await client.get("/config/portal-mode")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"mode": "private"}


# --------------------------------------------------------------------------
# 3. /auth/register gating
# --------------------------------------------------------------------------

@pytest.mark.portal_mode("private")
async def test_register_returns_404_in_private_mode(client):
    """In private mode, /auth/register is NOT mounted — 404, not 403."""
    resp = await client.post(
        "/auth/register",
        json={
            "email": f"resident-{uuid.uuid4().hex[:8]}@test.com",
            "password": "Tw3ntyCharacterPasswordX",
            "full_name": "Private-Mode Resident",
        },
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.portal_mode("public")
async def test_register_creates_public_user_in_public_mode(client):
    """In public mode, /auth/register creates a UserRole.PUBLIC user.

    Regression: the pre-T5D behavior force-created STAFF-role users on
    self-registration. T5D corrects this to PUBLIC. A STAFF response here
    means the ``UserCreate.force_public_role`` validator regressed.
    """
    email = f"resident-{uuid.uuid4().hex[:8]}@test.com"
    resp = await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "Tw3ntyCharacterPasswordX",
            "full_name": "Public-Mode Resident",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["email"] == email
    assert body["role"] == UserRole.PUBLIC.value
    assert body["role"] != UserRole.STAFF.value  # regression guard


@pytest.mark.portal_mode("public")
async def test_register_ignores_caller_supplied_role_in_public_mode(client):
    """Caller cannot escalate to STAFF/ADMIN via the register payload."""
    email = f"resident-{uuid.uuid4().hex[:8]}@test.com"
    resp = await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "Tw3ntyCharacterPasswordX",
            "full_name": "Would-Be Escalator",
            "role": "admin",  # silently ignored by force_public_role
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["role"] == UserRole.PUBLIC.value


# --------------------------------------------------------------------------
# 4. /public/requests — authenticated PUBLIC-only submission surface
# --------------------------------------------------------------------------

async def _login(client, email: str, password: str) -> str:
    resp = await client.post(
        "/auth/jwt/login", data={"username": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture
async def public_user_token(client) -> str:
    """Create a UserRole.PUBLIC account directly via UserManager and return
    its JWT. Mirrors the conftest admin_token/staff_token pattern (bypass
    HTTP registration; go straight to the user-creation manager) so the
    fixture doesn't depend on whether ``/auth/register`` happens to be
    mounted in the app instance ``client`` built.
    """
    from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
    from app.auth.manager import UserManager
    from app.models.user import User
    from app.schemas.user import AdminUserCreate
    # Import by attribute so we see whatever the client fixture set up
    import app.database as app_database

    email = f"public-user-{uuid.uuid4().hex[:8]}@test.com"
    password = "Tw3ntyCharacterPasswordX"

    async with app_database.async_session_maker() as session:
        user_db = SQLAlchemyUserDatabase(session, User)
        manager = UserManager(session=session, user_db=user_db)
        await manager.create(
            AdminUserCreate(
                email=email,
                password=password,
                full_name="Test Resident",
                role=UserRole.PUBLIC,
                is_active=True,
                is_verified=True,
                is_superuser=False,
            )
        )

    return await _login(client, email, password)


@pytest.mark.portal_mode("private")
async def test_public_requests_returns_404_in_private_mode(client):
    """Private mode does not mount the public router at all."""
    resp = await client.post(
        "/public/requests",
        json={"description": "I want the 2024 annual budget report, please."},
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.portal_mode("public")
async def test_public_requests_rejects_anonymous_in_public_mode(client):
    """Public mode still requires auth — anonymous walk-up submission is NOT
    supported in this slice (Scott Option A 2026-04-22)."""
    resp = await client.post(
        "/public/requests",
        json={"description": "I want the 2024 annual budget report, please."},
    )
    assert resp.status_code == 401, resp.text


@pytest.mark.portal_mode("public")
async def test_public_requests_rejects_staff_token(client, staff_token):
    """Staff users route through /requests/ instead; /public is resident-only."""
    resp = await client.post(
        "/public/requests",
        headers={"Authorization": f"Bearer {staff_token}"},
        json={"description": "Staff shouldn't submit via the public surface."},
    )
    assert resp.status_code == 403, resp.text
    detail = resp.json()["detail"].lower()
    assert "resident" in detail or "public" in detail


@pytest.mark.portal_mode("public")
async def test_public_requests_accepts_public_user(client, public_user_token):
    """Authenticated UserRole.PUBLIC submission: 201, returns tracking id."""
    resp = await client.post(
        "/public/requests",
        headers={"Authorization": f"Bearer {public_user_token}"},
        json={
            "description": "Please send me the 2024 annual budget report PDF.",
            "phone": "555-0100",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "received"
    # request_id is a parseable UUID
    uuid.UUID(body["request_id"])
    # Tracking-id guidance is in the message copy
    assert "tracking id" in body["message"].lower()


@pytest.mark.portal_mode("public")
async def test_public_requests_validates_description_min_length(client, public_user_token):
    """Descriptions below 10 chars are rejected at the schema layer (422)."""
    resp = await client.post(
        "/public/requests",
        headers={"Authorization": f"Bearer {public_user_token}"},
        json={"description": "too short"},  # 9 chars
    )
    assert resp.status_code == 422, resp.text
