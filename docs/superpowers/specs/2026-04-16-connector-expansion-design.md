# Connector Expansion Design
**Date:** 2026-04-16
**Project:** CivicRecords AI
**Status:** Approved — ready for implementation planning
**Spec ref:** UNIFIED-SPEC.md §11.4–11.5

---

## 1. Scope

### In this sprint
- `RestApiConnector` — generic REST connector (API key, Bearer/OAuth2, Basic auth)
- `OdbcConnector` — tabular data source via pyodbc (production) / sqlite3 adapter (tests)
- DB migration: `last_sync_cursor VARCHAR NULL` + `last_sync_at TIMESTAMPTZ NULL` on `data_sources`
- `test-connection` endpoint extended to handle `rest_api` and `odbc` source types
- Frontend wizard Step 2 branching updated for new connector types

### Out of scope (deferred)
- GIS REST API (Esri ArcGIS) — separate sprint
- Vendor SDK (Axon Evidence, CAD systems) — separate sprint
- SharePoint — use `RestApiConnector` with OAuth2 config; no custom connector needed
- Binary / multipart REST responses (e.g., file download endpoints) — v1 restricts to `json`, `xml`, and `csv` text formats only; binary blobs require a future `response_format: "binary"` mode and parser

---

## 2. Protocol Implementation

Both connectors extend `BaseConnector` and implement the 4-method universal protocol:
`authenticate()` / `discover()` / `fetch()` / `health_check()`

### 2.1 `_ensure_authenticated()` guard

Every protocol method (`discover`, `fetch`, `health_check`) calls `_ensure_authenticated()` as its first line. This method calls `authenticate()` if `self._authenticated` is False. Callers are never required to call `authenticate()` manually before using the connector. This makes the connector safe from any call site — not only the sync runner that follows the explicit `authenticate → discover → fetch` sequence.

### 2.2 RestApiConnector

**`authenticate()`**
- Validates required config fields are present.
- For OAuth2: exchanges `client_id` / `client_secret` at `token_url`; stores access token in `self._token` (in-memory only, never persisted). Records `self._token_expiry`.
- For API key / Bearer / Basic: sets `self._authenticated = True` immediately (credentials are supplied per-request, no pre-flight needed).
- Returns `bool`.

**`discover()`**
1. Calls `_ensure_authenticated()`.
2. Builds the request URL from `base_url + endpoint_path`.
3. Appends `since_field` query parameter if `last_sync_cursor` is set in config.
4. Paginates according to `pagination_style` (`page`, `offset`, `cursor`). For `none`, fetches one page only.
5. **`max_records` guard:** regardless of `pagination_style`, stops and logs a `WARNING` when the total discovered record count reaches `max_records` (default `10_000`). Log message: `"Discovery capped at {max_records} records — check pagination_style config"`. This prevents silent data loss when `pagination_style: "none"` is misconfigured against a paginated endpoint.
6. For each item in each page response, emits one `DiscoveredRecord`:
   - `source_path` = value at `record_id_field` JSON path (may be a full URL or a bare ID)
   - `filename` = synthesized from response metadata (e.g., `"record_{id}.json"`)
   - `mime_type` = hint derived from `response_format` (`"application/json"` / `"application/xml"` / `"text/csv"`). This is a discovery-stage hint only; the authoritative `mime_type` is set on `FetchedDocument` at fetch time from the same `response_format` field.
7. After all pages consumed (or `max_records` hit), updates `data_sources.last_sync_cursor` and `last_sync_at` **only on full successful completion** (see §2.6 cursor semantics).
8. Returns `list[DiscoveredRecord]`.

**`fetch(record: DiscoveredRecord)`**
1. Calls `_ensure_authenticated()`.
2. Constructs the fetch URL: if `source_path` is an absolute URL, uses it directly; otherwise appends to `base_url`.
3. GETs the record; returns `FetchedDocument` with `content = response_body_bytes` and `mime_type` derived from `response_format` (`"application/json"` / `"application/xml"` / `"text/csv"`).

**`health_check()`**
1. Calls `_ensure_authenticated()`.
2. Sends `HEAD` request to `base_url`.
3. **405 fallback:** if the response is `405 Method Not Allowed`, retries immediately with `GET`. Many municipal vendor APIs (Tyler Munis, Accela) do not implement `HEAD` and return `405` — a HEAD-only implementation would misdiagnose a healthy connection as failed. This fallback must be in the implementation, not just the plan.
4. Records latency.
5. Returns `HealthCheckResult` with `status`, `latency_ms`, and `error_message` if applicable.

### 2.3 OdbcConnector

**`authenticate()`**
- Calls `pyodbc.connect(connection_string)` (or the sqlite3 adapter in tests).
- Stores connection as `self._conn`.
- Returns `bool`.

**`discover()`**
1. Calls `_ensure_authenticated()`.
2. Builds table reference: `{schema_name}.{table_name}` if `schema_name` is set, otherwise `{table_name}`.
3. If `modified_column` is set and `last_sync_cursor` is set:
   `SELECT {pk_column}, {modified_column} FROM {table_ref} WHERE {modified_column} > ? ORDER BY {modified_column}`
   with `last_sync_cursor` as the bind parameter.
4. If `modified_column` is None or `last_sync_cursor` is None: full table scan (no WHERE clause).
5. Emits one `DiscoveredRecord` per row:
   - `source_path` = `"{table_name}/{pk_value}"`
   - `filename` = `"{table_name}_{pk_value}.json"`
   - `mime_type` = `"application/json"`
6. Updates cursor **only on full successful completion** (see §2.5).
7. Returns `list[DiscoveredRecord]`.

**`fetch(record: DiscoveredRecord)`**
1. Calls `_ensure_authenticated()`.
2. Parses `source_path` to extract table name and PK value.
3. Executes `SELECT * FROM {table_ref} WHERE {pk_column} = ?`.
4. Serializes the row to JSON bytes (`json.dumps(dict(row))`).
5. Returns `FetchedDocument` with `content = json_bytes`, `mime_type = "application/json"`.

**`health_check()`**
1. Calls `_ensure_authenticated()`.
2. Executes `SELECT 1` (or dialect-appropriate no-op).
3. Returns `HealthCheckResult`.

### 2.4 429 retry policy

When any REST request (in `discover()`, `fetch()`, or `health_check()`) receives a `429 Too Many Requests` response, the connector applies exponential backoff with jitter:

- **Max attempts:** 3 (initial attempt + 2 retries)
- **Base delay:** 1 second; doubled each attempt (1s → 2s → 4s)
- **Jitter:** ±20% random jitter applied to each delay to prevent thundering herd
- **Max total wait:** 30 seconds — if the next retry would exceed this ceiling, raise immediately
- **`Retry-After` header:** if present, use its value (seconds) as the delay instead of the computed backoff, subject to the 30s ceiling
- **Non-retriable errors:** 4xx other than 429, 5xx — these are raised immediately without retry. 5xx failures are not retried in-process because sync runs are idempotent and a transient infrastructure failure is absorbed by the next scheduled run; retrying in-process would extend the failure window without improving the outcome.

This policy must be implemented as a shared utility (e.g., `connectors/retry.py`) used by both `RestApiConnector` and any future HTTP-based connectors. It must not be re-implemented per connector.

### 2.5 OAuth2 token refresh

`_ensure_authenticated()` checks `self._token_expiry` before returning for OAuth2 connectors. If the token is expired (or within 60 seconds of expiry), it re-authenticates transparently. Token is stored in instance variables only — never written to the database or logs.

### 2.6 Cursor semantics — partial sync failure

`last_sync_cursor` and `last_sync_at` on `data_sources` advance **only after full successful completion** of a sync run — meaning `discover()` returned all records AND all `fetch()` calls succeeded.

If `fetch()` fails on any record mid-run, the cursor is **not advanced**. The next sync run starts from the same cursor position, re-discovers the full record set from the last known good point, and retries failed fetches. This is the safe behavior: records may be re-processed (idempotent ingestion handles duplicates), but no records are silently skipped.

This semantics decision must be enforced at the sync runner level (in `ingestion/tasks.py`), not inside the connector itself. The connector is stateless with respect to cursor writes; the caller writes the cursor only on confirmed success.

---

## 3. Config Schemas

Both config types are Pydantic models with `connector_type` as the discriminator field. They are stored AES-256 encrypted in `data_sources.connection_config` (existing field).

### 3.1 `RestApiConfig`

```python
class RestApiConfig(BaseModel):
    connector_type: Literal["rest_api"]
    base_url: str
    endpoint_path: str                          # e.g., "/api/v1/records"
    auth_method: Literal["api_key", "bearer", "oauth2", "basic", "none"]

    # api_key auth
    api_key: str | None = None
    key_header: str = "X-API-Key"              # header name
    key_location: Literal["header", "query"] = "header"

    # bearer auth
    token: str | None = None

    # oauth2 auth
    token_url: str | None = None
    client_id: str | None = None
    client_secret: str | None = None           # credential — masked in UI after save
    scope: str | None = None

    # basic auth
    username: str | None = None
    password: str | None = None                # credential — masked in UI after save

    # pagination
    pagination_style: Literal["page", "offset", "cursor", "none"] = "none"
    pagination_params: dict = {}               # key names for page/limit/cursor in query string
    record_id_field: str = "id"               # JSON path to unique record identifier
    since_field: str | None = None            # query param name for incremental sync

    # response format
    response_format: Literal["json", "xml", "csv"] = "json"
    # Governs how fetch() deserializes the response body before returning FetchedDocument.
    # "json" (default): response bytes passed through as-is; mime_type = "application/json"
    # "xml":  response bytes passed through as-is; mime_type = "application/xml"
    # "csv":  response bytes passed through as-is; mime_type = "text/csv"
    # The ingestion pipeline must have a parser registered for the chosen format.
    # Binary / multipart responses are out of scope for v1 (document in §1).

    # safety cap
    max_records: int = 10_000
```

### 3.2 `ODBCConfig`

```python
class ODBCConfig(BaseModel):
    connector_type: Literal["odbc"]
    connection_string: str      # CREDENTIAL — masked in UI after save, never returned in API responses
                                # JDBC URLs and DSNs frequently embed credentials inline.
                                # Treat identically to api_key and client_secret.
    schema_name: str | None = None   # PostgreSQL/SQL Server/Oracle schema; None = default schema
    table_name: str
    pk_column: str
    modified_column: str | None = None   # None = full re-sync every run
```

### 3.3 UI masking requirement

`api_key`, `client_secret`, `password` (RestApiConfig), and `connection_string` (ODBCConfig) must be masked in the wizard after save — displayed as `••••••••` with no way to reveal the value. This is an existing spec §11.5 requirement. The `connection_string` field is the highest-risk for future frontend developers treating it as "just a config string" — it must be explicitly flagged in frontend code with a comment.

---

## 4. Database Migration

One migration covers REST, ODBC, and future IMAP incremental sync.

`last_sync_cursor` stores an opaque string: ISO timestamp for time-based sync, page token for cursor-based pagination, or IMAP UID watermark (future). No semantic parsing at the DB layer.

### 4.1 Alembic migration (upgrade + downgrade)

Both functions are required. `alembic downgrade -1` must work cleanly for a city IT admin hitting a bad deployment.

```python
def upgrade() -> None:
    op.add_column("data_sources",
        sa.Column("last_sync_cursor", sa.String(), nullable=True))
    op.add_column("data_sources",
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True))

def downgrade() -> None:
    op.drop_column("data_sources", "last_sync_at")
    op.drop_column("data_sources", "last_sync_cursor")
```

---

## 5. Test Strategy

### 5.1 `test_rest_connector.py` — using `respx`

`respx` intercepts at the HTTP transport layer. Real connector code runs against controlled responses.

Required test cases:
- `test_api_key_auth` — header and query param placement
- `test_bearer_auth`
- `test_oauth2_auth` — token exchange, in-memory storage, token refresh on expiry
- `test_basic_auth`
- `test_discover_pagination_page` — multi-page traversal, correct DiscoveredRecord output
- `test_discover_pagination_cursor` — cursor-based traversal
- `test_discover_max_records_cap` — verifies warning logged and discovery stops at `max_records`
- `test_discover_429_retry` — connector retries on rate limit
- `test_discover_empty_page_terminates` — stops cleanly on empty response
- `test_fetch_absolute_url` — source_path is a full URL
- `test_fetch_relative_id` — source_path is a bare ID appended to base_url
- `test_health_check_head_success`
- `test_health_check_head_405_falls_back_to_get` — asserts no false failure on 405
- `test_partial_sync_cursor_not_advanced` — fetch fails on record N; asserts last_sync_cursor unchanged
- `test_connection_safety` — calls test-connection path; asserts: (1) `data_sources.connection_config` is byte-for-byte unchanged in the DB, (2) no credential field values (`api_key`, `client_secret`, `password`, `token`) appear anywhere in any `AuditLog.details` JSONB entry written during the call. The `AuditLog` model (`audit_log` table) is a real queryable SQLAlchemy model — query it directly: `session.query(AuditLog).filter(AuditLog.action == "test_connection").all()`. The credential containment check **must recursively walk all nested string values** in each `.details` dict, including values inside arrays and sub-objects at any depth (e.g., `details["request_context"]["headers"]["Authorization"]`), and fail if any credential string appears as a substring of any string value at any depth. A flat `entry.details.get("api_key")` check is insufficient and must not be used.

### 5.2 `test_odbc_connector.py` — using sqlite3 adapter

A pytest fixture swaps `pyodbc.connect` for `sqlite3.connect`. Real SQL executes against a real in-memory SQLite database. Mocking cursor methods is explicitly avoided — that tests nothing about the SQL being generated.

Required test cases:
- `test_discover_full_scan` — seeds table, runs discover, asserts exact DiscoveredRecord list
- `test_discover_incremental` — seeds table with modified_at, sets cursor, asserts only newer rows returned
- `test_discover_with_schema_name` — verifies `{schema}.{table}` qualification in generated SQL
- `test_fetch_row` — asserts correct JSON serialization of fetched row
- `test_health_check`
- `test_partial_sync_cursor_not_advanced` — fetch fails mid-run; cursor remains at pre-run value
- `test_connection_safety` — same assertion as REST variant: `connection_config` unchanged in DB; `connection_string` value does not appear as a substring of any string value at any depth in any `AuditLog.details` JSONB entry written during the call (recursive walk required — same helper as REST variant)

### 5.3 Cursor semantics test (both connectors)

The `test_partial_sync_cursor_not_advanced` test must:
1. Run `discover()` — returns N records.
2. Simulate `fetch()` failure on record `N/2`.
3. Assert `data_sources.last_sync_cursor` equals the pre-run value (not the post-discover value).
4. Assert records `N/2 + 1` through `N` are not marked as ingested.

This assertion belongs in `test_ingestion_tasks.py` (the sync runner), not the connector unit test, since cursor writes happen at the runner level.

---

## 6. Wiring Checklist

- [ ] `backend/app/connectors/rest_api.py` — RestApiConnector implementation
- [ ] `backend/app/connectors/odbc.py` — OdbcConnector implementation
- [ ] `backend/app/connectors/__init__.py` — register both new types in the connector factory
- [ ] `backend/app/schemas/` — RestApiConfig and ODBCConfig Pydantic models
- [ ] `backend/app/datasources/router.py` — extend `test-connection` for `rest_api` and `odbc`
- [ ] `backend/alembic/versions/` — migration adding `last_sync_cursor` and `last_sync_at`
- [ ] `backend/app/ingestion/tasks.py` — cursor write only on full success
- [ ] `frontend/` — wizard Step 2 branching for new connector types; mask `connection_string`
- [ ] `backend/tests/test_rest_connector.py`
- [ ] `backend/tests/test_odbc_connector.py`
- [ ] `backend/tests/test_ingestion_tasks.py` — partial sync failure cursor test
- [ ] `docs/UNIFIED-SPEC.md` — update §11.4 REST API and ODBC/JDBC from [PLANNED] to [IMPLEMENTED]
- [ ] `CHANGELOG.md` — entry for connector expansion
