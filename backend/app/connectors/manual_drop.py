"""Manual/Export Drop Connector — watched folder for department file drops.

Universal fallback for systems with no API, no database access, and no email
export. Departments place files in a designated drop folder; the connector
discovers new files, ingests them, and moves processed files to an archive
subdirectory to prevent re-ingestion.

Per canonical spec section 12.4: "Manual / Export Drop — Systems with no API,
clerk uploads [MVP-NOW]."
"""

import hashlib
import logging
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from app.connectors.base import (
    BaseConnector,
    DiscoveredRecord,
    FetchedDocument,
    HealthCheckResult,
    HealthStatus,
)

logger = logging.getLogger(__name__)

# File types accepted for ingestion (matching the ingestion pipeline)
ACCEPTED_EXTENSIONS = frozenset({
    ".pdf", ".docx", ".xlsx", ".xls", ".csv",
    ".txt", ".html", ".htm", ".eml", ".mbox",
    ".jpg", ".jpeg", ".png", ".tiff", ".tif",
})

# Max file size: 100 MB (matching upload endpoint limit)
MAX_FILE_BYTES = 100 * 1024 * 1024


class ManualDropConnector(BaseConnector):
    """Connector for watched drop folders.

    Config keys:
        drop_path: Directory path to watch for new files
        archive_processed: Move processed files to archive subfolder (default True)
        recursive: Scan subdirectories (default False)
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self._drop_dir: Path | None = None
        self._archive_dir: Path | None = None

    @property
    def connector_type(self) -> str:
        return "manual_drop"

    async def authenticate(self) -> bool:
        """Verify the drop directory exists and is readable."""
        drop_path = self.config.get("drop_path", "")
        if not drop_path:
            logger.error("ManualDrop: drop_path not configured")
            return False

        self._drop_dir = Path(drop_path)
        if not self._drop_dir.is_dir():
            logger.error("ManualDrop: drop_path does not exist: %s", drop_path)
            return False

        if not self._drop_dir.stat():
            logger.error("ManualDrop: drop_path is not accessible: %s", drop_path)
            return False

        # Create archive subdirectory if archiving is enabled
        if self.config.get("archive_processed", True):
            self._archive_dir = self._drop_dir / "_processed"
            self._archive_dir.mkdir(exist_ok=True)

        self._authenticated = True
        logger.info("ManualDrop: configured for %s", drop_path)
        return True

    async def discover(self) -> list[DiscoveredRecord]:
        """List files in the drop folder that are eligible for ingestion."""
        if not self._drop_dir or not self._authenticated:
            raise RuntimeError("Not authenticated — call authenticate() first")

        recursive = self.config.get("recursive", False)
        pattern = "**/*" if recursive else "*"

        records = []
        skipped = 0

        for file_path in self._drop_dir.glob(pattern):
            # Skip directories, archive folder, and hidden files
            if file_path.is_dir():
                continue
            if self._archive_dir and self._archive_dir in file_path.parents:
                continue
            if file_path.name.startswith("."):
                continue

            # Check extension
            ext = file_path.suffix.lower()
            if ext not in ACCEPTED_EXTENSIONS:
                logger.debug("ManualDrop: skipping unsupported type: %s", file_path.name)
                skipped += 1
                continue

            # Check size
            try:
                stat = file_path.stat()
            except OSError:
                continue

            if stat.st_size > MAX_FILE_BYTES:
                logger.warning(
                    "ManualDrop: skipping oversized file (%.1f MB): %s",
                    stat.st_size / 1024 / 1024, file_path.name,
                )
                skipped += 1
                continue

            if stat.st_size == 0:
                continue

            records.append(DiscoveredRecord(
                source_path=str(file_path),
                filename=file_path.name,
                file_type=ext.lstrip("."),
                file_size=stat.st_size,
                last_modified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                metadata={
                    "relative_path": str(file_path.relative_to(self._drop_dir)),
                },
            ))

        if skipped:
            logger.info("ManualDrop: %d files skipped (unsupported type or too large)", skipped)
        logger.info("ManualDrop: %d eligible files found in %s", len(records), self._drop_dir)
        return records

    async def fetch(self, source_path: str) -> FetchedDocument:
        """Read a file from the drop folder."""
        file_path = Path(source_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {source_path}")

        content = file_path.read_bytes()
        ext = file_path.suffix.lower().lstrip(".")

        return FetchedDocument(
            source_path=source_path,
            filename=file_path.name,
            file_type=ext,
            content=content,
            file_size=len(content),
            metadata={
                "sha256": hashlib.sha256(content).hexdigest(),
            },
        )

    def archive_file(self, source_path: str) -> Path | None:
        """Move a processed file to the archive subdirectory.

        Returns the new path, or None if archiving is disabled.
        """
        if not self._archive_dir:
            return None

        file_path = Path(source_path)
        if not file_path.exists():
            return None

        # Preserve relative path structure in archive
        if self._drop_dir and self._drop_dir in file_path.parents:
            relative = file_path.relative_to(self._drop_dir)
        else:
            relative = Path(file_path.name)

        dest = self._archive_dir / relative
        dest.parent.mkdir(parents=True, exist_ok=True)

        # Add timestamp suffix if file already exists in archive
        if dest.exists():
            stem = dest.stem
            suffix = dest.suffix
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            dest = dest.with_name(f"{stem}_{timestamp}{suffix}")

        shutil.move(str(file_path), str(dest))
        logger.info("ManualDrop: archived %s → %s", file_path.name, dest)
        return dest

    async def health_check(self) -> HealthCheckResult:
        """Check that the drop directory is accessible."""
        if not self._drop_dir:
            return HealthCheckResult(
                status=HealthStatus.UNREACHABLE,
                error_message="Not configured",
            )

        start = time.monotonic()
        try:
            if not self._drop_dir.is_dir():
                return HealthCheckResult(
                    status=HealthStatus.FAILED,
                    error_message=f"Directory does not exist: {self._drop_dir}",
                )

            # Count available files
            count = sum(1 for f in self._drop_dir.iterdir() if f.is_file() and not f.name.startswith("."))
            latency = int((time.monotonic() - start) * 1000)

            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                latency_ms=latency,
                records_available=count,
            )
        except Exception as exc:
            return HealthCheckResult(
                status=HealthStatus.FAILED,
                error_message=str(exc),
            )
