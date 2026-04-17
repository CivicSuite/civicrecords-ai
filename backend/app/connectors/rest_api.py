"""REST API Connector.

Connects to generic REST APIs to discover and fetch records.
Supports: API key (header/query), Bearer token, OAuth2 client credentials, Basic auth.
Pagination: none, page-based, offset-based, cursor-based.
"""

import json
import logging
import time
import urllib.parse
from typing import Any, Optional

import httpx

from app.connectors.base import (
    BaseConnector,
    DiscoveredRecord,
    FetchedDocument,
    HealthCheckResult,
    HealthStatus,
)
from app.connectors.retry import RetryExhausted, with_retry
from app.schemas.connectors.rest_api import RestApiConfig

logger = logging.getLogger(__name__)

_MIME_TYPES = {
    "json": "application/json",
    "xml": "application/xml",
    "csv": "text/csv",
}


def _extract_dotted(obj: Any, path: str | None) -> Any:
    """Traverse a dotted path into obj. None path returns obj unchanged.

    Raises KeyError if a segment is missing.
    Raises TypeError if a segment traverses a non-dict.
    """
    if path is None:
        return obj
    for segment in path.split("."):
        if not isinstance(obj, dict):
            raise TypeError(
                f"_extract_dotted: expected dict at segment '{segment}', got {type(obj).__name__}"
            )
        if segment not in obj:
            raise KeyError(
                f"_extract_dotted: key '{segment}' not found in object. "
                f"Available keys (first 10): {list(obj.keys())[:10]}"
            )
        obj = obj[segment]
    return obj


def _build_source_path(base_url: str, endpoint_path: str, record_id: str) -> str:
    """Construct canonical source_path for a REST record.

    Format: {base_url.rstrip('/')}{endpoint_path}/{url_encoded_record_id}
    Max 2048 chars enforced at call site (validation layer).
    """
    base = str(base_url).rstrip("/")
    encoded_id = urllib.parse.quote(str(record_id), safe="")
    return f"{base}{endpoint_path}/{encoded_id}"


class RestApiConnector(BaseConnector):
    """Generic REST API connector supporting multiple auth methods and pagination styles."""

    def __init__(self, config: dict | RestApiConfig) -> None:
        super().__init__(config if isinstance(config, dict) else config.model_dump())
        if isinstance(config, dict):
            self._cfg = RestApiConfig(**config)
        else:
            self._cfg = config
        self._client: Optional[httpx.AsyncClient] = None
        self._authenticated = False
        self._access_token: Optional[str] = None  # OAuth2 token cache

    @property
    def connector_type(self) -> str:
        return "rest_api"

    def _ensure_authenticated(self) -> None:
        if not self._authenticated:
            raise RuntimeError(
                "RestApiConnector: call authenticate() before using the connector"
            )

    def _auth_headers(self) -> dict[str, str]:
        cfg = self._cfg
        if cfg.auth_method == "api_key" and cfg.key_location == "header":
            return {cfg.key_header: cfg.api_key or ""}
        if cfg.auth_method == "bearer":
            return {"Authorization": f"Bearer {cfg.token}"}
        if cfg.auth_method == "oauth2":
            return {"Authorization": f"Bearer {self._access_token or ''}"}
        return {}

    def _auth_params(self) -> dict[str, str]:
        cfg = self._cfg
        if cfg.auth_method == "api_key" and cfg.key_location == "query":
            return {cfg.key_header: cfg.api_key or ""}
        return {}

    def _base_headers(self) -> dict[str, str]:
        mime = _MIME_TYPES.get(self._cfg.response_format, "application/json")
        return {"Accept": mime, **self._auth_headers()}

    async def _fetch_oauth2_token(self) -> str:
        cfg = self._cfg
        assert cfg.token_url and cfg.client_id and cfg.client_secret
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                str(cfg.token_url),
                data={
                    "grant_type": "client_credentials",
                    "client_id": cfg.client_id,
                    "client_secret": cfg.client_secret,
                },
            )
            resp.raise_for_status()
            return resp.json()["access_token"]

    async def authenticate(self) -> bool:
        cfg = self._cfg
        try:
            if cfg.auth_method == "oauth2":
                self._access_token = await self._fetch_oauth2_token()
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                auth=httpx.BasicAuth(cfg.username or "", cfg.password or "")
                if cfg.auth_method == "basic"
                else None,
            )
            self._authenticated = True
            return True
        except Exception as exc:
            logger.error("RestApiConnector authentication failed: %s", exc)
            return False

    async def _make_request(
        self,
        method: str,
        url: str,
        *,
        params: dict | None = None,
        bypass_retry: bool = False,
    ) -> httpx.Response:
        assert self._client is not None

        async def _action() -> httpx.Response:
            return await self._client.request(  # type: ignore[union-attr]
                method,
                url,
                headers=self._base_headers(),
                params={**self._auth_params(), **(params or {})},
            )

        try:
            response = await with_retry(_action, bypass_retry=bypass_retry)
        except RetryExhausted as exc:
            raise RuntimeError(f"Request to {url} failed after retries: {exc}") from exc

        # 429 Rate-limit: honor Retry-After header, cap at 600s (D10)
        if response.status_code == 429:
            import asyncio
            retry_after = int(response.headers.get("Retry-After", "30"))
            wait = min(retry_after, 600)
            logger.warning(
                "RestApiConnector: 429 rate-limited, waiting %ds (Retry-After: %s)",
                wait, retry_after,
            )
            await asyncio.sleep(wait)
            try:
                response = await with_retry(_action, bypass_retry=bypass_retry)
            except RetryExhausted as exc:
                raise RuntimeError(f"Request to {url} failed after 429 retry: {exc}") from exc

        # Reactive 401 refresh — OAuth2 only
        if response.status_code == 401 and self._cfg.auth_method == "oauth2":
            logger.info("OAuth2 token expired, refreshing")
            self._access_token = await self._fetch_oauth2_token()
            try:
                response = await with_retry(_action, bypass_retry=bypass_retry)
            except RetryExhausted as exc:
                raise RuntimeError(f"Request to {url} failed after token refresh: {exc}") from exc

        return response

    def _endpoint_url(self) -> str:
        return str(self._cfg.base_url).rstrip("/") + self._cfg.endpoint_path

    async def discover(self, since: str | None = None) -> list[DiscoveredRecord]:
        self._ensure_authenticated()
        cfg = self._cfg
        url = self._endpoint_url()
        records: list[DiscoveredRecord] = []
        page = 1
        offset = 0
        cursor: str | None = None

        while True:
            params: dict[str, Any] = {}

            if cfg.since_field and since:
                params[cfg.since_field] = since

            if cfg.pagination_style == "page":
                params[cfg.page_param] = page
                params[cfg.limit_param] = cfg.page_size
            elif cfg.pagination_style == "offset":
                params[cfg.offset_param] = offset
                params[cfg.limit_param] = cfg.page_size
            elif cfg.pagination_style == "cursor" and cursor:
                params[cfg.cursor_field] = cursor

            response = await self._make_request("GET", url, params=params)
            response.raise_for_status()

            # Size guard
            if len(response.content) > cfg.max_response_bytes:
                raise RuntimeError(
                    f"Response size {len(response.content)} exceeds "
                    f"max_response_bytes={cfg.max_response_bytes}"
                )

            data = response.json()

            # Extract records list
            if cfg.results_field:
                items = data.get(cfg.results_field, [])
            elif isinstance(data, list):
                items = data
            else:
                items = [data]

            for item in items:
                record_id = str(item.get(cfg.id_field, len(records)))
                source_path = _build_source_path(str(cfg.base_url), cfg.endpoint_path, record_id)
                records.append(
                    DiscoveredRecord(
                        source_path=source_path,
                        filename=f"{urllib.parse.quote(record_id, safe='')}.json",
                        file_type="json",
                        file_size=len(json.dumps(item).encode()),
                        metadata={"raw": item},
                    )
                )

            if len(records) >= cfg.max_records:
                logger.warning(
                    "RestApiConnector: max_records cap (%d) reached, stopping discovery",
                    cfg.max_records,
                )
                records = records[: cfg.max_records]
                break

            # Pagination advance / exit
            if cfg.pagination_style == "none":
                break
            elif cfg.pagination_style == "page":
                if len(items) < cfg.page_size:
                    break
                page += 1
            elif cfg.pagination_style == "offset":
                if len(items) < cfg.page_size:
                    break
                offset += len(items)
            elif cfg.pagination_style == "cursor":
                next_cursor = data.get(cfg.cursor_field) if isinstance(data, dict) else None
                if not next_cursor:
                    break
                cursor = next_cursor

        return records

    async def fetch(self, source_path: str) -> FetchedDocument:
        self._ensure_authenticated()
        response = await self._make_request("GET", source_path)
        response.raise_for_status()

        raw_bytes = response.content
        if len(raw_bytes) > self._cfg.max_response_bytes:
            raise RuntimeError(
                f"Fetch response size {len(raw_bytes)} exceeds "
                f"max_response_bytes={self._cfg.max_response_bytes}"
            )

        # Canonical serialization: extract via data_key, sort keys, deterministic output
        parsed = response.json()
        record = _extract_dotted(parsed, self._cfg.data_key)
        canonical = json.dumps(record, sort_keys=True, ensure_ascii=False, default=str)
        content = canonical.encode("utf-8")

        # Second size check for canonical content (default=str can enlarge output)
        if len(content) > self._cfg.max_response_bytes:
            raise RuntimeError(
                f"Canonical content size {len(content)} exceeds "
                f"max_response_bytes={self._cfg.max_response_bytes}"
            )

        return FetchedDocument(
            source_path=source_path,
            filename=source_path.rstrip("/").split("/")[-1] + ".json",
            file_type=self._cfg.response_format,
            content=content,
            file_size=len(content),
            metadata={"url": source_path},
        )

    async def health_check(self) -> HealthCheckResult:
        self._ensure_authenticated()
        url = self._endpoint_url()
        start = time.monotonic()
        try:
            response = await self._make_request("HEAD", url, bypass_retry=True)
            if response.status_code == 405:
                # HEAD not allowed — fall back to GET
                response = await self._make_request("GET", url, bypass_retry=True)
            latency_ms = int((time.monotonic() - start) * 1000)
            if response.status_code < 400:
                return HealthCheckResult(
                    status=HealthStatus.HEALTHY,
                    latency_ms=latency_ms,
                )
            return HealthCheckResult(
                status=HealthStatus.FAILED,
                latency_ms=latency_ms,
                error_message=f"HTTP {response.status_code}",
            )
        except Exception as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            return HealthCheckResult(
                status=HealthStatus.UNREACHABLE,
                latency_ms=latency_ms,
                error_message=str(exc),
            )

    def close(self) -> None:
        """httpx.AsyncClient is GC-safe; aclose() requires async context."""
        pass
