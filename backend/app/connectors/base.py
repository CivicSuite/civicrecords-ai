"""Universal Connector Protocol — Base Class.

Every connector implements 4 operations:
- authenticate(): Establish secure connection
- discover(): Enumerate available records
- fetch(): Pull specific records into standard format
- health_check(): Verify connection alive and healthy
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    UNREACHABLE = "unreachable"


@dataclass
class HealthCheckResult:
    status: HealthStatus
    latency_ms: int | None = None
    error_message: str | None = None
    records_available: int | None = None
    schema_hash: str | None = None
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DiscoveredRecord:
    """A record discovered in a source system."""
    source_path: str
    filename: str
    file_type: str
    file_size: int
    last_modified: datetime | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class FetchedDocument:
    """A document fetched from a source system, ready for ingestion."""
    source_path: str
    filename: str
    file_type: str
    content: bytes
    file_size: int
    metadata: dict = field(default_factory=dict)


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
