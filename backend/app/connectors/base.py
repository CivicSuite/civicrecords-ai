"""Universal Connector Protocol — Base Class.

Every connector implements 4 operations:
- authenticate(): Establish secure connection
- discover(): Enumerate available records
- fetch(): Pull specific records into standard format
- health_check(): Verify connection alive and healthy
"""

from abc import ABC, abstractmethod

from civiccore.ingest import DiscoveredRecord, FetchedDocument, HealthCheckResult, HealthStatus

__all__ = [
    "BaseConnector",
    "DiscoveredRecord",
    "FetchedDocument",
    "HealthCheckResult",
    "HealthStatus",
]


class BaseConnector(ABC):
    """Abstract base class for all data source connectors."""

    def __init__(self, config: dict):
        """Initialize with connection configuration.

        Args:
            config: Connection-specific configuration (paths, credentials, etc.)
        """
        self.config = config
        self._authenticated = False

    def close(self) -> None:
        """Release connector resources. Subclasses override for stateful connections."""
        pass

    @property
    @abstractmethod
    def connector_type(self) -> str:
        """Return the connector type identifier (e.g., 'file_system', 'smtp', 'rest_api')."""
        ...

    @abstractmethod
    async def authenticate(self) -> bool:
        """Establish connection to the source system.

        Returns:
            True if authentication successful, False otherwise.
        """
        ...

    @abstractmethod
    async def discover(self) -> list[DiscoveredRecord]:
        """Enumerate available records in the source system.

        Returns:
            List of discovered records with metadata.
        """
        ...

    @abstractmethod
    async def fetch(self, source_path: str) -> FetchedDocument:
        """Fetch a specific record from the source system.

        Args:
            source_path: Path/identifier of the record to fetch.

        Returns:
            FetchedDocument with content bytes and metadata.
        """
        ...

    @abstractmethod
    async def health_check(self) -> HealthCheckResult:
        """Check connection health.

        Returns:
            HealthCheckResult with status, latency, and diagnostics.
        """
        ...
