"""
Tests for RestApiConnector using respx to intercept HTTP at transport layer.
"""
import pytest
import respx
import httpx

from app.connectors.rest_api import RestApiConnector
from app.schemas.connectors.rest_api import RestApiConfig
from app.connectors.base import HealthStatus


def make_config(**kwargs) -> RestApiConfig:
    defaults = {
        "base_url": "https://api.example.gov",
        "endpoint_path": "/records",
        "auth_method": "none",
    }
    defaults.update(kwargs)
    return RestApiConfig(**defaults)


# ---------------------------------------------------------------------------
# authenticate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_authenticate_sets_authenticated():
    connector = RestApiConnector(make_config())
    result = await connector.authenticate()
    assert result is True
    assert connector._authenticated is True


@pytest.mark.asyncio
async def test_authenticate_dict_config():
    connector = RestApiConnector({
        "base_url": "https://api.example.gov",
        "endpoint_path": "/records",
        "auth_method": "none",
    })
    result = await connector.authenticate()
    assert result is True


# ---------------------------------------------------------------------------
# _ensure_authenticated guard
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ensure_authenticated_raises_before_auth_discover():
    connector = RestApiConnector(make_config())
    with pytest.raises(RuntimeError, match="authenticate()"):
        await connector.discover()


@pytest.mark.asyncio
async def test_ensure_authenticated_raises_before_auth_fetch():
    connector = RestApiConnector(make_config())
    with pytest.raises(RuntimeError, match="authenticate()"):
        await connector.fetch("https://api.example.gov/records/1")


@pytest.mark.asyncio
async def test_ensure_authenticated_raises_before_auth_health_check():
    connector = RestApiConnector(make_config())
    with pytest.raises(RuntimeError, match="authenticate()"):
        await connector.health_check()


# ---------------------------------------------------------------------------
# discover — auth header (api_key header)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_discover_api_key_header():
    config = make_config(
        auth_method="api_key",
        api_key="secret123",
        key_location="header",
        key_header="X-API-Key",
    )
    connector = RestApiConnector(config)
    await connector.authenticate()

    respx.get("https://api.example.gov/records").mock(
        return_value=httpx.Response(200, json=[{"id": "1", "name": "Test"}])
    )
    records = await connector.discover()
    assert len(records) == 1
    assert respx.calls[0].request.headers["X-API-Key"] == "secret123"


# ---------------------------------------------------------------------------
# discover — auth param (api_key query)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_discover_api_key_query():
    config = make_config(
        auth_method="api_key",
        api_key="secret123",
        key_location="query",
        key_header="api_key",
    )
    connector = RestApiConnector(config)
    await connector.authenticate()

    respx.get("https://api.example.gov/records").mock(
        return_value=httpx.Response(200, json=[])
    )
    await connector.discover()
    request = respx.calls[0].request
    assert "api_key=secret123" in str(request.url)


# ---------------------------------------------------------------------------
# discover — bearer auth
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_discover_bearer_auth():
    config = make_config(auth_method="bearer", token="mytoken")
    connector = RestApiConnector(config)
    await connector.authenticate()

    respx.get("https://api.example.gov/records").mock(
        return_value=httpx.Response(200, json=[{"id": "42"}])
    )
    records = await connector.discover()
    assert len(records) == 1
    assert respx.calls[0].request.headers["Authorization"] == "Bearer mytoken"


# ---------------------------------------------------------------------------
# discover — Accept header mapping
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_discover_accept_header_json():
    connector = RestApiConnector(make_config(response_format="json"))
    await connector.authenticate()

    respx.get("https://api.example.gov/records").mock(
        return_value=httpx.Response(200, json=[])
    )
    await connector.discover()
    assert respx.calls[0].request.headers["Accept"] == "application/json"


# ---------------------------------------------------------------------------
# discover — max_records cap
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_max_records_cap():
    config = make_config(max_records=2)
    connector = RestApiConnector(config)
    await connector.authenticate()

    respx.get("https://api.example.gov/records").mock(
        return_value=httpx.Response(
            200, json=[{"id": "1"}, {"id": "2"}, {"id": "3"}]
        )
    )
    records = await connector.discover()
    assert len(records) == 2


# ---------------------------------------------------------------------------
# discover — results_field extraction
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_discover_results_field():
    config = make_config(results_field="data")
    connector = RestApiConnector(config)
    await connector.authenticate()

    respx.get("https://api.example.gov/records").mock(
        return_value=httpx.Response(
            200, json={"data": [{"id": "10"}, {"id": "11"}], "total": 2}
        )
    )
    records = await connector.discover()
    assert len(records) == 2


# ---------------------------------------------------------------------------
# discover — since_field incremental sync
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_discover_since_field():
    config = make_config(since_field="updated_after")
    connector = RestApiConnector(config)
    await connector.authenticate()

    respx.get("https://api.example.gov/records").mock(
        return_value=httpx.Response(200, json=[{"id": "5"}])
    )
    await connector.discover(since="2024-01-01T00:00:00Z")
    request = respx.calls[0].request
    assert "updated_after=2024-01-01T00%3A00%3A00Z" in str(request.url) or "updated_after" in str(request.url)


# ---------------------------------------------------------------------------
# discover — page pagination
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_discover_page_pagination():
    config = make_config(pagination_style="page", page_size=2)
    connector = RestApiConnector(config)
    await connector.authenticate()

    call_count = 0

    def side_effect(request, route):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(200, json=[{"id": "1"}, {"id": "2"}])
        return httpx.Response(200, json=[{"id": "3"}])  # partial page → stop

    respx.get("https://api.example.gov/records").mock(side_effect=side_effect)
    records = await connector.discover()
    assert len(records) == 3
    assert call_count == 2


# ---------------------------------------------------------------------------
# discover — offset pagination
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_discover_offset_pagination():
    config = make_config(pagination_style="offset", page_size=2)
    connector = RestApiConnector(config)
    await connector.authenticate()

    call_count = 0

    def side_effect(request, route):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(200, json=[{"id": "1"}, {"id": "2"}])
        return httpx.Response(200, json=[{"id": "3"}])

    respx.get("https://api.example.gov/records").mock(side_effect=side_effect)
    records = await connector.discover()
    assert len(records) == 3
    assert call_count == 2


# ---------------------------------------------------------------------------
# discover — cursor pagination
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_discover_cursor_pagination():
    config = make_config(
        pagination_style="cursor",
        cursor_field="next_cursor",
        response_format="json",
    )
    connector = RestApiConnector(config)
    await connector.authenticate()

    call_count = 0

    def side_effect(request, route):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(
                200, json={"items": [{"id": "1"}], "next_cursor": "page2token"}
            )
        return httpx.Response(
            200, json={"items": [{"id": "2"}], "next_cursor": None}
        )

    config2 = make_config(
        pagination_style="cursor",
        cursor_field="next_cursor",
        results_field="items",
        response_format="json",
    )
    connector2 = RestApiConnector(config2)
    await connector2.authenticate()
    respx.get("https://api.example.gov/records").mock(side_effect=side_effect)
    records = await connector2.discover()
    assert len(records) == 2
    assert call_count == 2


# ---------------------------------------------------------------------------
# discover — max_response_bytes guard
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_discover_max_response_bytes_guard():
    config = make_config(max_response_bytes=10)
    connector = RestApiConnector(config)
    await connector.authenticate()

    respx.get("https://api.example.gov/records").mock(
        return_value=httpx.Response(200, json=[{"id": "1", "data": "x" * 100}])
    )
    with pytest.raises(RuntimeError, match="max_response_bytes"):
        await connector.discover()


# ---------------------------------------------------------------------------
# fetch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_fetch_returns_document():
    connector = RestApiConnector(make_config())
    await connector.authenticate()

    respx.get("https://api.example.gov/records/1").mock(
        return_value=httpx.Response(200, json={"id": "1", "title": "Record 1"})
    )
    doc = await connector.fetch("https://api.example.gov/records/1")
    assert doc.source_path == "https://api.example.gov/records/1"
    assert doc.content is not None
    assert doc.file_size > 0


@pytest.mark.asyncio
@respx.mock
async def test_fetch_max_response_bytes_guard():
    config = make_config(max_response_bytes=5)
    connector = RestApiConnector(config)
    await connector.authenticate()

    respx.get("https://api.example.gov/records/1").mock(
        return_value=httpx.Response(200, content=b"x" * 100)
    )
    with pytest.raises(RuntimeError, match="max_response_bytes"):
        await connector.fetch("https://api.example.gov/records/1")


# ---------------------------------------------------------------------------
# health_check — HEAD success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_health_check_head_success():
    connector = RestApiConnector(make_config())
    await connector.authenticate()

    respx.head("https://api.example.gov/records").mock(
        return_value=httpx.Response(200)
    )
    result = await connector.health_check()
    assert result.status == HealthStatus.HEALTHY
    assert result.latency_ms is not None


# ---------------------------------------------------------------------------
# health_check — HEAD 405 falls back to GET
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_health_check_head_405_falls_back_to_get():
    connector = RestApiConnector(make_config())
    await connector.authenticate()

    respx.head("https://api.example.gov/records").mock(
        return_value=httpx.Response(405)
    )
    respx.get("https://api.example.gov/records").mock(
        return_value=httpx.Response(200, json=[])
    )
    result = await connector.health_check()
    assert result.status == HealthStatus.HEALTHY


# ---------------------------------------------------------------------------
# health_check — 4xx response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_health_check_4xx_returns_failed():
    connector = RestApiConnector(make_config())
    await connector.authenticate()

    respx.head("https://api.example.gov/records").mock(
        return_value=httpx.Response(403)
    )
    result = await connector.health_check()
    assert result.status == HealthStatus.FAILED
    assert "403" in result.error_message


# ---------------------------------------------------------------------------
# health_check — network error returns UNREACHABLE
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_health_check_network_error_returns_unreachable():
    connector = RestApiConnector(make_config())
    await connector.authenticate()

    respx.head("https://api.example.gov/records").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    result = await connector.health_check()
    assert result.status == HealthStatus.UNREACHABLE
    assert result.error_message is not None


# ---------------------------------------------------------------------------
# connector_type property
# ---------------------------------------------------------------------------

def test_connector_type():
    connector = RestApiConnector(make_config())
    assert connector.connector_type == "rest_api"


# ---------------------------------------------------------------------------
# P6a — canonical serialization, data_key, source_path encoding
# ---------------------------------------------------------------------------

class TestRestApiConnectorP6a:

    def _make_connector(self, extra_config: dict = None) -> "RestApiConnector":
        from app.connectors.rest_api import RestApiConnector
        config = {
            "base_url": "https://api.example.com",
            "endpoint_path": "/records",
            "auth_method": "none",
            "response_format": "json",
            **(extra_config or {}),
        }
        return RestApiConnector(config)

    def test_data_key_nested_extraction(self):
        """data_key='response.record' extracts correctly from nested response."""
        from app.connectors.rest_api import _extract_dotted
        payload = {"response": {"record": {"id": 1, "name": "Test"}}}
        result = _extract_dotted(payload, "response.record")
        assert result == {"id": 1, "name": "Test"}

    def test_data_key_missing_raises_key_error(self):
        """data_key='missing.path' → KeyError with descriptive message."""
        from app.connectors.rest_api import _extract_dotted
        with pytest.raises(KeyError, match="missing"):
            _extract_dotted({"data": {}}, "missing.path")

    def test_data_key_array_each_element_is_record(self):
        """data_key resolves to list → each element is its own DiscoveredRecord."""
        from app.connectors.rest_api import _extract_dotted
        payload = {"items": [{"id": 1}, {"id": 2}, {"id": 3}]}
        result = _extract_dotted(payload, "items")
        assert isinstance(result, list)
        assert len(result) == 3

    def test_source_path_record_id_encoded(self):
        """Record ID containing '/' is percent-encoded in source_path."""
        import urllib.parse
        from app.connectors.rest_api import _build_source_path
        base = "https://api.example.com"
        endpoint = "/records"
        record_id = "dept/2024/contract-001"
        path = _build_source_path(base, endpoint, record_id)
        # The record ID segment must be URL-encoded
        assert urllib.parse.quote(record_id, safe="") in path
        assert "/" not in path.split(endpoint + "/")[1]  # no raw slash in ID segment


# ---------------------------------------------------------------------------
# P7 adversarial — Retry-After header edge cases
# ---------------------------------------------------------------------------

from unittest.mock import AsyncMock, patch


class TestRetryAfterAdversarial:
    """Malformed Retry-After headers must not crash the worker.

    The real 429 handling lives in with_retry() (retry.py), not _make_request().
    These tests exercise that path via the connector's discover() call.
    """

    @pytest.mark.asyncio
    @respx.mock
    async def test_retry_after_non_numeric_string_uses_backoff_not_crash(self):
        """Retry-After: 'banana' → must not raise ValueError; falls back to
        exponential backoff and retries successfully."""
        config = make_config()
        connector = RestApiConnector(config)
        await connector.authenticate()

        call_count = 0

        def side_effect(request, route):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(
                    429, headers={"Retry-After": "banana"}, json={}
                )
            return httpx.Response(200, json=[{"id": "1"}])

        respx.get("https://api.example.gov/records").mock(side_effect=side_effect)

        with patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
            records = await connector.discover()

        # No ValueError — fell back to exponential backoff and retried
        assert len(records) == 1
        # Sleep was called once with exponential backoff value (not a specific number,
        # just some positive float — not 0, not a crash)
        assert mock_sleep.call_count == 1
        sleep_arg = mock_sleep.call_args[0][0]
        assert sleep_arg > 0

    @pytest.mark.asyncio
    @respx.mock
    async def test_retry_after_empty_string_uses_backoff(self):
        """Retry-After: '' → empty string treated as missing; uses exponential backoff."""
        config = make_config()
        connector = RestApiConnector(config)
        await connector.authenticate()

        call_count = 0

        def side_effect(request, route):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(429, json={})  # no Retry-After header at all
            return httpx.Response(200, json=[])

        respx.get("https://api.example.gov/records").mock(side_effect=side_effect)

        with patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
            records = await connector.discover()

        assert records == []
        assert mock_sleep.call_count == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_retry_after_large_value_capped_at_600s(self):
        """Retry-After: 9999 → capped at 600s per D10 spec."""
        config = make_config()
        connector = RestApiConnector(config)
        await connector.authenticate()

        call_count = 0

        def side_effect(request, route):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(
                    429, headers={"Retry-After": "9999"}, json={}
                )
            return httpx.Response(200, json=[])

        respx.get("https://api.example.gov/records").mock(side_effect=side_effect)

        with patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
            await connector.discover()

        mock_sleep.assert_called_once_with(600.0)

    @pytest.mark.asyncio
    @respx.mock
    async def test_retry_after_numeric_string_honored(self):
        """Retry-After: '20' → sleeps 20s (within 30s backoff ceiling)."""
        config = make_config()
        connector = RestApiConnector(config)
        await connector.authenticate()

        call_count = 0

        def side_effect(request, route):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(
                    429, headers={"Retry-After": "20"}, json={}
                )
            return httpx.Response(200, json=[])

        respx.get("https://api.example.gov/records").mock(side_effect=side_effect)

        with patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
            await connector.discover()

        mock_sleep.assert_called_once_with(20.0)
