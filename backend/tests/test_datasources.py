import uuid
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_datasource(client: AsyncClient, admin_token: str):
    resp = await client.post("/datasources/", json={"name": f"test-source-{uuid.uuid4().hex[:8]}", "source_type": "directory", "connection_config": {"path": "/data/test"}}, headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["source_type"] == "directory"
    assert data["is_active"] is True

@pytest.mark.asyncio
async def test_create_datasource_requires_admin(client: AsyncClient, staff_token: str):
    resp = await client.post("/datasources/", json={"name": "test", "source_type": "upload"}, headers={"Authorization": f"Bearer {staff_token}"})
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_list_datasources(client: AsyncClient, admin_token: str):
    await client.post("/datasources/", json={"name": f"list-test-{uuid.uuid4().hex[:8]}", "source_type": "upload"}, headers={"Authorization": f"Bearer {admin_token}"})
    resp = await client.get("/datasources/", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert len(resp.json()) >= 1

@pytest.mark.asyncio
async def test_ingestion_stats(client: AsyncClient, admin_token: str):
    resp = await client.get("/datasources/stats", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "total_sources" in data
    assert "total_documents" in data
    assert "total_chunks" in data


@pytest.mark.asyncio
async def test_health_status_degraded_on_failure_count(client: AsyncClient, admin_token: str, db_session):
    """consecutive_failure_count > 0 → health_status=degraded in list response."""
    from sqlalchemy import text
    source_id = uuid.uuid4()
    await db_session.execute(text("""
        INSERT INTO data_sources
          (id, name, source_type, connection_config, is_active,
           sync_schedule, schedule_enabled, sync_paused,
           consecutive_failure_count, created_by)
        VALUES (:id, :name, 'rest_api', '{}', true,
                NULL, true, false, 3,
                (SELECT id FROM users LIMIT 1))
    """), {"id": str(source_id), "name": f"health-degraded-{source_id.hex[:8]}"})
    await db_session.commit()

    resp = await client.get("/datasources/", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    src = next((s for s in resp.json() if s["id"] == str(source_id)), None)
    assert src is not None, "Seeded source not found in list response"
    assert src["health_status"] == "degraded"
    assert src["consecutive_failure_count"] == 3


@pytest.mark.asyncio
async def test_health_status_circuit_open_when_paused(client: AsyncClient, admin_token: str, db_session):
    """sync_paused=True → health_status=circuit_open."""
    from sqlalchemy import text
    source_id = uuid.uuid4()
    await db_session.execute(text("""
        INSERT INTO data_sources
          (id, name, source_type, connection_config, is_active,
           sync_schedule, schedule_enabled, sync_paused,
           consecutive_failure_count, created_by)
        VALUES (:id, :name, 'rest_api', '{}', true,
                NULL, true, true, 5,
                (SELECT id FROM users LIMIT 1))
    """), {"id": str(source_id), "name": f"health-paused-{source_id.hex[:8]}"})
    await db_session.commit()

    resp = await client.get("/datasources/", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    src = next((s for s in resp.json() if s["id"] == str(source_id)), None)
    assert src is not None, "Seeded source not found in list response"
    assert src["health_status"] == "circuit_open"


@pytest.mark.asyncio
async def test_health_status_healthy_default(client: AsyncClient, admin_token: str):
    """A freshly created source has health_status=healthy."""
    resp = await client.post(
        "/datasources/",
        json={"name": f"healthy-src-{uuid.uuid4().hex[:8]}", "source_type": "rest_api",
              "connection_config": {}},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    source_id = resp.json()["id"]

    list_resp = await client.get("/datasources/", headers={"Authorization": f"Bearer {admin_token}"})
    src = next((s for s in list_resp.json() if s["id"] == source_id), None)
    assert src is not None
    assert src["health_status"] == "healthy"
    assert src["active_failure_count"] == 0


# --- T2B response-shape redaction tests ---
SENSITIVE_FIELDS = {"connection_config", "api_key", "token", "password", "client_secret", "database_url"}


@pytest.mark.asyncio
async def test_staff_list_datasources_no_connection_config(client: AsyncClient, admin_token: str, staff_token: str):
    """GET /datasources/ returns DataSourceRead (redacted) — connection_config absent for staff."""
    await client.post(
        "/datasources/",
        json={"name": f"redact-test-{uuid.uuid4().hex[:8]}", "source_type": "rest_api",
              "connection_config": {"api_key": "secret-value", "base_url": "https://example.com"}},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = await client.get("/datasources/", headers={"Authorization": f"Bearer {staff_token}"})
    assert resp.status_code == 200
    for src in resp.json():
        for field in SENSITIVE_FIELDS:
            assert field not in src, f"Sensitive field '{field}' found in staff list response"


@pytest.mark.asyncio
async def test_admin_list_datasources_no_connection_config(client: AsyncClient, admin_token: str):
    """GET /datasources/ returns redacted shape even for admins — connection_config absent."""
    resp = await client.get("/datasources/", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    for src in resp.json():
        assert "connection_config" not in src, "connection_config must not appear in list response"


@pytest.mark.asyncio
async def test_admin_create_datasource_returns_connection_config(client: AsyncClient, admin_token: str):
    """POST /datasources/ returns DataSourceAdminRead — connection_config present for admin."""
    config = {"api_key": "secret-value", "base_url": "https://example.com"}
    resp = await client.post(
        "/datasources/",
        json={"name": f"admin-create-{uuid.uuid4().hex[:8]}", "source_type": "rest_api",
              "connection_config": config},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "connection_config" in data, "Admin create response must include connection_config"
    assert data["connection_config"] == config


@pytest.mark.asyncio
async def test_admin_update_datasource_returns_connection_config(client: AsyncClient, admin_token: str):
    """PATCH /datasources/{id} returns DataSourceAdminRead — connection_config present for admin."""
    create_resp = await client.post(
        "/datasources/",
        json={"name": f"admin-patch-{uuid.uuid4().hex[:8]}", "source_type": "rest_api",
              "connection_config": {"api_key": "old-secret"}},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert create_resp.status_code == 201
    source_id = create_resp.json()["id"]

    new_config = {"api_key": "new-secret", "base_url": "https://updated.example.com"}
    patch_resp = await client.patch(
        f"/datasources/{source_id}",
        json={"connection_config": new_config},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert "connection_config" in data, "Admin update response must include connection_config"
    assert data["connection_config"] == new_config
