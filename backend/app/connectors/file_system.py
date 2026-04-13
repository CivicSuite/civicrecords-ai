"""File System / SMB Connector.

Connects to local or mounted file directories to discover and fetch documents.
Supports: PDF, DOCX, XLSX, CSV, TXT, HTML, EML
"""

import logging
import os
import hashlib
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

from app.connectors.base import (
    BaseConnector,
    DiscoveredRecord,
    FetchedDocument,
    HealthCheckResult,
    HealthStatus,
)


SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".xlsx", ".csv", ".txt", ".html", ".htm", ".eml",
    ".doc", ".xls", ".json", ".xml", ".rtf",
}


class FileSystemConnector(BaseConnector):
    """Connector for local file system and mounted network shares."""

    @property
    def connector_type(self) -> str:
        return "file_system"

    def __init__(self, config: dict):
        super().__init__(config)
        self.base_path = config.get("path", "")
        self.recursive = config.get("recursive", True)
        self.max_file_size = config.get("max_file_size_mb", 50) * 1024 * 1024

    async def authenticate(self) -> bool:
        """Verify the directory exists and is readable."""
        path = Path(self.base_path)
        if path.exists() and path.is_dir() and os.access(path, os.R_OK):
            self._authenticated = True
            return True
        return False

    async def discover(self) -> list[DiscoveredRecord]:
        """Scan directory for supported files."""
        if not self._authenticated:
            await self.authenticate()

        records = []
        base = Path(self.base_path)

        if self.recursive:
            files = base.rglob("*")
        else:
            files = base.glob("*")

        for file_path in files:
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue

            stat = file_path.stat()
            if stat.st_size > self.max_file_size:
                logger.warning(
                    "Skipping large file (%.1f MB > limit %.1f MB): %s",
                    stat.st_size / 1024 / 1024,
                    self.max_file_size / 1024 / 1024,
                    file_path,
                )
                continue

            records.append(DiscoveredRecord(
                source_path=str(file_path),
                filename=file_path.name,
                file_type=file_path.suffix.lstrip(".").lower(),
                file_size=stat.st_size,
                last_modified=datetime.fromtimestamp(stat.st_mtime),
                metadata={
                    "relative_path": str(file_path.relative_to(base)),
                },
            ))

        return records

    async def fetch(self, source_path: str) -> FetchedDocument:
        """Read a file from the filesystem."""
        path = Path(source_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {source_path}")
        if not path.is_file():
            raise ValueError(f"Not a file: {source_path}")

        content = path.read_bytes()
        return FetchedDocument(
            source_path=source_path,
            filename=path.name,
            file_type=path.suffix.lstrip(".").lower(),
            content=content,
            file_size=len(content),
            metadata={
                "sha256": hashlib.sha256(content).hexdigest(),
                "last_modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
            },
        )

    async def health_check(self) -> HealthCheckResult:
        """Check if directory is accessible."""
        start = time.monotonic()
        path = Path(self.base_path)

        if not path.exists():
            return HealthCheckResult(
                status=HealthStatus.UNREACHABLE,
                error_message=f"Directory does not exist: {self.base_path}",
                latency_ms=int((time.monotonic() - start) * 1000),
            )

        if not os.access(path, os.R_OK):
            return HealthCheckResult(
                status=HealthStatus.FAILED,
                error_message=f"Directory not readable: {self.base_path}",
                latency_ms=int((time.monotonic() - start) * 1000),
            )

        # Count files for records_available
        try:
            file_count = sum(
                1 for f in path.rglob("*")
                if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
            )
        except PermissionError:
            return HealthCheckResult(
                status=HealthStatus.DEGRADED,
                error_message="Some subdirectories not readable",
                latency_ms=int((time.monotonic() - start) * 1000),
            )

        return HealthCheckResult(
            status=HealthStatus.HEALTHY,
            records_available=file_count,
            latency_ms=int((time.monotonic() - start) * 1000),
        )
