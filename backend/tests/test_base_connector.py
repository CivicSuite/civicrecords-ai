import pytest
from app.connectors.base import BaseConnector, DiscoveredRecord, FetchedDocument, HealthCheckResult, HealthStatus


class _MinimalConnector(BaseConnector):
    @property
    def connector_type(self) -> str:
        return "test"

    async def authenticate(self) -> bool:
        return True

    async def discover(self) -> list[DiscoveredRecord]:
        return []

    async def fetch(self, source_path: str) -> FetchedDocument:
        raise NotImplementedError

    async def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(status=HealthStatus.HEALTHY, latency_ms=0)


def test_base_connector_close_is_noop():
    """close() must exist and be callable without error on the base class."""
    c = _MinimalConnector(config={})
    c.close()  # must not raise AttributeError or any other error


from app.connectors import get_connector


def test_factory_rest_api():
    connector = get_connector("rest_api", {
        "base_url": "https://example.gov",
        "endpoint_path": "/records",
        "auth_method": "none",
    })
    assert connector.connector_type == "rest_api"


def test_factory_odbc():
    connector = get_connector("odbc", {
        "connection_string": "Server=db.example.gov;Database=x",
        "table_name": "records",
        "pk_column": "id",
    })
    assert connector.connector_type == "odbc"


def test_factory_unknown_raises():
    with pytest.raises(ValueError, match="Unknown connector type"):
        get_connector("gis", {})
