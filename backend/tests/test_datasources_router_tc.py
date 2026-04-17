"""
Unit tests for test-connection endpoint safety:
- Credential scrubbing
- Recursive JSONB credential walk (no flat .get() allowed)
- Pollution detection (non-deterministic REST API responses)
"""
import pytest
from app.datasources.router import _scrub_error


CREDENTIAL_FIELDS = {"api_key", "token", "client_secret", "password", "connection_string"}


def _find_credentials_recursive(obj, path="root"):
    """
    Recursively walk a JSON-like object and return all paths where
    a credential field name appears as a dict key.
    """
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in CREDENTIAL_FIELDS:
                found.append(f"{path}.{k}")
            found.extend(_find_credentials_recursive(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            found.extend(_find_credentials_recursive(item, f"{path}[{i}]"))
    return found


def test_scrub_error_removes_api_key():
    msg = "Failed: api_key=secretvalue123"
    scrubbed = _scrub_error(msg)
    assert "secretvalue123" not in scrubbed
    assert "api_key" in scrubbed


def test_scrub_error_removes_password():
    msg = "connection_string=DSN=prod;Password=hunter2;UID=admin"
    scrubbed = _scrub_error(msg)
    assert "hunter2" not in scrubbed


def test_recursive_walk_flat():
    response = {"success": True, "latency_ms": 42, "status": "healthy"}
    found = _find_credentials_recursive(response)
    assert found == [], f"Credential fields found in response: {found}"


def test_recursive_walk_nested():
    """Simulate a response that accidentally nested a config object."""
    response = {
        "success": True,
        "details": {
            "connector": {
                "api_key": "leaked!",
                "base_url": "https://example.gov",
            }
        }
    }
    found = _find_credentials_recursive(response)
    assert "root.details.connector.api_key" in found


def test_recursive_walk_in_list():
    response = {
        "records": [
            {"id": 1, "password": "oops"},
            {"id": 2, "title": "safe"},
        ]
    }
    found = _find_credentials_recursive(response)
    assert "root.records[0].password" in found


class TestTestConnectionPollutionDetection:

    @pytest.mark.asyncio
    async def test_test_connection_pollution_warning(self, client, admin_token):
        """test-connection with two differing fetches → success=True + warning: non_deterministic_response."""
        from unittest.mock import patch, AsyncMock, MagicMock
        from app.connectors.base import HealthCheckResult, HealthStatus

        with patch("app.connectors.rest_api.RestApiConnector.authenticate", new_callable=AsyncMock, return_value=True), \
             patch("app.connectors.rest_api.RestApiConnector.health_check", new_callable=AsyncMock,
                   return_value=HealthCheckResult(status=HealthStatus.HEALTHY, latency_ms=5)), \
             patch("app.connectors.rest_api.RestApiConnector.discover", new_callable=AsyncMock,
                   return_value=[MagicMock(source_path="records/1")]), \
             patch("app.datasources.router._double_fetch_hashes") as mock_dfh:
            # Make _double_fetch_hashes an async mock
            async def _async_dfh(*args, **kwargs):
                return ("aaa111", "bbb222", ["fetched_at", "request_id"])
            mock_dfh.side_effect = _async_dfh

            resp = await client.post(
                "/datasources/test-connection",
                json={
                    "source_type": "rest_api",
                    "rest_api_config": {
                        "base_url": "https://api.example.com",
                        "endpoint_path": "/records",
                        "auth_method": "none",
                        "response_format": "json",
                        "data_key": "data",
                    },
                },
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body.get("warning") == "non_deterministic_response"
        assert "differing_keys" in body
        assert "fetched_at" in body["differing_keys"]

    @pytest.mark.asyncio
    async def test_test_connection_no_pollution_warning(self, client, admin_token):
        """Two identical fetches → no warning field in response."""
        from unittest.mock import patch, AsyncMock, MagicMock
        from app.connectors.base import HealthCheckResult, HealthStatus

        with patch("app.connectors.rest_api.RestApiConnector.authenticate", new_callable=AsyncMock, return_value=True), \
             patch("app.connectors.rest_api.RestApiConnector.health_check", new_callable=AsyncMock,
                   return_value=HealthCheckResult(status=HealthStatus.HEALTHY, latency_ms=5)), \
             patch("app.connectors.rest_api.RestApiConnector.discover", new_callable=AsyncMock,
                   return_value=[MagicMock(source_path="records/1")]), \
             patch("app.datasources.router._double_fetch_hashes") as mock_dfh:
            async def _async_dfh(*args, **kwargs):
                return ("aaa111", "aaa111", [])
            mock_dfh.side_effect = _async_dfh

            resp = await client.post(
                "/datasources/test-connection",
                json={
                    "source_type": "rest_api",
                    "rest_api_config": {
                        "base_url": "https://api.example.com",
                        "endpoint_path": "/records",
                        "auth_method": "none",
                        "response_format": "json",
                    },
                },
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "warning" not in body or body.get("warning") is None
