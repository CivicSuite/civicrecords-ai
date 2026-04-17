import json
import logging
import re
import time
import urllib.parse
from typing import Any, Optional

try:
    import pyodbc
except ModuleNotFoundError:  # pragma: no cover
    pyodbc = None  # type: ignore[assignment]

from app.connectors.base import (
    BaseConnector,
    DiscoveredRecord,
    FetchedDocument,
    HealthCheckResult,
    HealthStatus,
)
from app.schemas.connectors.odbc import ODBCConfig

logger = logging.getLogger(__name__)

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_SCRUB_PATTERNS = [
    re.compile(r"(Password\s*=\s*)[^\s;]+", re.IGNORECASE),
    re.compile(r"(PWD\s*=\s*)[^\s;]+", re.IGNORECASE),
    re.compile(r"(UID\s*=\s*)[^\s;]+", re.IGNORECASE),
    re.compile(r"(User\s*ID\s*=\s*)[^\s;]+", re.IGNORECASE),
]


def _scrub_dsn_error(message: str) -> str:
    """Remove credential components from ODBC error messages."""
    for pattern in _SCRUB_PATTERNS:
        message = pattern.sub(r"\g<1>[REDACTED]", message)
    return message


def _validate_identifier(value: str, field_name: str) -> str:
    """Defense-in-depth identifier check at query construction time."""
    if not _IDENTIFIER_RE.match(value):
        raise ValueError(
            f"Invalid SQL identifier for {field_name}: {value!r}. "
            f"Must match ^[A-Za-z_][A-Za-z0-9_]*$"
        )
    return value


class OdbcConnector(BaseConnector):
    """Tabular data connector via pyodbc. Each row becomes a JSON document."""

    def __init__(self, config: dict | ODBCConfig) -> None:
        super().__init__(config if isinstance(config, dict) else config.model_dump())
        if isinstance(config, dict):
            self._cfg = ODBCConfig(**config)
        else:
            self._cfg = config
        self._connection: Optional[Any] = None
        self._authenticated = False

    @property
    def connector_type(self) -> str:
        return "odbc"

    def _ensure_authenticated(self) -> None:
        if not self._authenticated:
            raise RuntimeError(
                "OdbcConnector: call authenticate() before using the connector"
            )

    async def authenticate(self) -> bool:
        try:
            self._connection = pyodbc.connect(self._cfg.connection_string)
            self._authenticated = True
            return True
        except Exception as exc:
            logger.error(
                "OdbcConnector authentication failed: %s",
                _scrub_dsn_error(str(exc)),
            )
            return False

    def _build_select_query(
        self,
        columns: Optional[list[str]],
        table_name: str,
        pk_column: str,
        modified_column: Optional[str],
        since: Optional[str],
        batch_size: int,
        offset: int,
    ) -> tuple[str, list[Any]]:
        """Build SELECT query with identifier validation (defense-in-depth)."""
        _validate_identifier(table_name, "table_name")
        _validate_identifier(pk_column, "pk_column")

        if columns:
            cols = ", ".join(
                _validate_identifier(c, f"column[{i}]") for i, c in enumerate(columns)
            )
        else:
            cols = "*"

        params: list[Any] = []
        where_clause = ""
        if modified_column and since:
            _validate_identifier(modified_column, "modified_column")
            where_clause = f" WHERE {modified_column} > ?"
            params.append(since)

        # Use LIMIT/OFFSET (ANSI-compatible with SQLite, MySQL, PostgreSQL).
        # For SQL Server use OFFSET … FETCH — callers on SQL Server should
        # set batch_size large enough to avoid pagination issues, or subclass.
        query = (
            f"SELECT {cols} FROM {table_name}"
            f"{where_clause}"
            f" ORDER BY {pk_column}"
            f" LIMIT ? OFFSET ?"
        )
        params.extend([batch_size, offset])
        return query, params

    async def discover(self, since: str | None = None) -> list[DiscoveredRecord]:
        self._ensure_authenticated()
        cfg = self._cfg
        assert self._connection is not None

        records: list[DiscoveredRecord] = []
        offset = 0

        while True:
            query, params = self._build_select_query(
                columns=cfg.columns,
                table_name=cfg.table_name,
                pk_column=cfg.pk_column,
                modified_column=cfg.modified_column,
                since=since,
                batch_size=cfg.batch_size,
                offset=offset,
            )
            try:
                cursor = self._connection.cursor()
                cursor.execute(query, params)
                columns_meta = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
            except Exception as exc:
                raise RuntimeError(
                    f"OdbcConnector discover() query failed: "
                    f"{_scrub_dsn_error(str(exc))}"
                ) from exc

            if not rows:
                break

            for row in rows:
                row_dict = dict(zip(columns_meta, row))
                pk_value = str(row_dict.get(cfg.pk_column, len(records)))
                content = json.dumps(row_dict, default=str).encode()

                if len(content) > cfg.max_row_bytes:
                    logger.warning(
                        "OdbcConnector: row %s size %d exceeds max_row_bytes=%d, skipping",
                        pk_value,
                        len(content),
                        cfg.max_row_bytes,
                    )
                    continue

                # URL-encode PK to safely handle '/', spaces, '%', and other special chars
                encoded_pk = urllib.parse.quote(str(pk_value), safe="")
                records.append(
                    DiscoveredRecord(
                        source_path=f"{cfg.table_name}/{encoded_pk}",
                        filename=f"{encoded_pk}.json",
                        file_type="json",
                        file_size=len(content),
                        metadata={"pk": pk_value},
                    )
                )

            if len(rows) < cfg.batch_size:
                break
            offset += cfg.batch_size

        return records

    async def fetch(self, source_path: str) -> FetchedDocument:
        self._ensure_authenticated()
        cfg = self._cfg
        assert self._connection is not None

        # Extract and decode pk from source_path: "table_name/url_encoded_pk"
        parts = source_path.split("/", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid source_path format: {source_path!r}")
        pk_value = urllib.parse.unquote(parts[1])  # decode before SQL binding

        _validate_identifier(cfg.table_name, "table_name")
        _validate_identifier(cfg.pk_column, "pk_column")

        query = f"SELECT * FROM {cfg.table_name} WHERE {cfg.pk_column} = ?"
        try:
            cursor = self._connection.cursor()
            cursor.execute(query, [pk_value])
            columns_meta = [desc[0] for desc in cursor.description]
            row = cursor.fetchone()
        except Exception as exc:
            raise RuntimeError(
                f"OdbcConnector fetch() failed: {_scrub_dsn_error(str(exc))}"
            ) from exc

        if row is None:
            raise FileNotFoundError(f"Record not found: {source_path}")

        row_dict = dict(zip(columns_meta, row))

        # Canonical serialization: exclude modified_column (if set), sort keys
        if cfg.modified_column is not None:
            row_dict.pop(cfg.modified_column, None)
        canonical = json.dumps(row_dict, sort_keys=True, ensure_ascii=False, default=str)
        content = canonical.encode("utf-8")

        if len(content) > cfg.max_row_bytes:
            raise RuntimeError(
                f"Row {pk_value!r} size {len(content)} exceeds "
                f"max_row_bytes={cfg.max_row_bytes}"
            )

        return FetchedDocument(
            source_path=source_path,
            filename=f"{urllib.parse.quote(str(pk_value), safe='')}.json",
            file_type="json",
            content=content,
            file_size=len(content),
            metadata={"pk": pk_value, "table": cfg.table_name},
        )

    async def health_check(self) -> HealthCheckResult:
        self._ensure_authenticated()
        assert self._connection is not None
        start = time.monotonic()
        try:
            cursor = self._connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            latency_ms = int((time.monotonic() - start) * 1000)
            return HealthCheckResult(status=HealthStatus.HEALTHY, latency_ms=latency_ms)
        except Exception as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            return HealthCheckResult(
                status=HealthStatus.FAILED,
                latency_ms=latency_ms,
                error_message=_scrub_dsn_error(str(exc)),
            )

    def close(self) -> None:
        if self._connection:
            try:
                self._connection.close()
            except Exception:
                pass
            self._connection = None
            self._authenticated = False
