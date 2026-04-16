# Connector Expansion Design — v4
**Date:** 2026-04-16
**Revised:** 2026-04-16
**Project:** CivicRecords AI
**Status:** Pending final approval — ready for implementation planning
**Spec ref:** UNIFIED-SPEC.md §11.4–11.5
**Supersedes:** `2026-04-16-connector-expansion-design-v3.md`

**Revision history:**
- v1 — initial design doc
- v2 — Alembic downgrade, 429 retry, response_format, recursive JSONB walk, renumbering, 5xx rationale, discover() mime_type hint
- v3 — Tier 1: SQL injection guard, token masking, connection-string scrubbing, test-connection spec, cursor/JSON restriction, expires_in fallback, pagination_params schema. Tier 2: read-only contract, close() lifecycle, discriminated union, XML/CSV tests, audit-entry assertion, reactive 401, response size, write-only boundary, retry on health_check, since_field format, scope wire format. Tier 3 plan-level notes.
- v4 — §2.7/§2.5 timeout conflict resolved (test-connection bypasses retry); BaseConnector.close() in §6 wiring; 401 reactive refresh scoped to OAuth2 only; close() tests moved to test_ingestion_tasks.py; ODBC row size guard added; per-request HTTP timeout specified; DSN component scrubbing for belt-and-suspenders; §2.8 per-fetch aggregate clarification.

---

## 1. Scope

### In this sprint
- `RestApiConnector` — generic REST connector (API key, Bearer/OAuth2, Basic auth)
- `OdbcConnector` — tabular data source via pyodbc (production) / sqlite3 adapter (tests)
- DB migration: `last_sync_cursor VARCHAR NULL` + `last_sync_at TIMESTAMPTZ NULL` on `data_sources`
- `test-connection` endpoint extended to handle `rest_api` and `odbc` source types (see §2.7)
- Frontend wizard Step 2 branching updated for new connector types
- `connectors/retry.py` — shared HTTP retry utility (§2.5)

### Out of scope (deferred)
- GIS REST API (Esri ArcGIS) — separate sprint
- Vendor SDK (Axon Evidence, CAD systems) — separate sprint
- SharePoint — use `RestApiConnector` with OAuth2 config; no custom connector needed
- Binary / multipart REST responses — v1 restricts to `json`, `xml`, `csv`; binary blobs require a future `response_format: "binary"` mode

### Plan-level notes (Tier 3 — resolved in implementation plan, not spec)
- `backend/tests/test_retry.py` must be included in the test plan
- After `upgrade()`, existing `data_sources` rows retain NULL for both new columns; existing connectors trigger a full re-sync on first run (expected, not a bug)
- Structured error logging format for failed `fetch()` calls: `error_class`, `record_id`, `status_code`, `retry_count` — specify in plan
- Celery `soft_time_limit` / `time_limit` must be set explicitly in the plan, accounting for `max_records = 10_000` worst case
- ODBC schema evolution (changing table columns) is admin-managed in v1; `SELECT *` will silently produce different JSON — document in USER-MANUAL
- A `docs/superpowers/specs/INDEX.md` pointing to the current active spec version is recommended

---

## 2. Protocol Implementation

Both connectors extend `BaseConnector` and implement the 4-method universal protocol:
`authenticate()` / `discover()` / `fetch()` / `health_check()`

### 2.1 `_ensure_authenticated()` guard

Every protocol method (`discover`, `fetch`, `health_check`) calls `_ensure_authenticated()` as its first line. This method calls `authenticate()` if `self._authenticated` is False. Callers are never required to call `authenticate()` manually before using the connector.

### 2.2 Connector contract invariants

These invariants apply to ALL connectors, present and future:

**Read-only verbs:** `discover()` and `fetch()` MUST use only GET or HEAD. POST/PUT/PATCH/DELETE are prohibited, even on "read" endpoints that require a POST body.

**Write-only credentials at the API boundary:** `api_key`, `client_secret`, `password`, `token` (RestApiConfig) and `connection_string` (ODBCConfig) are write-only. They MUST NOT be returned in any GET API response under any circumstance — the field is omitted entirely from serialized responses.

**Connection lifecycle:** Every connector that allocates a stateful connection in `authenticate()` MUST implement `close()` to release it. The sync runner MUST call `close()` in a `finally` block. The `BaseConnector` base class provides a default no-op `close()` so existing connectors (`file_system`, `imap_email`, `manual_drop`) can be called by the sync runner without `AttributeError`. Only connectors holding a stateful connection override it.

**No credential logging:** Credential field values must never appear in log lines at any level. The ODBC connector error-scrubbing requirement (§2.4) extends this to exception messages.

### 2.3 RestApiConnector

**`authenticate()`**
- Validates required config fields are present.
- For OAuth2: exchanges `client_id` / `client_secret` at `token_url` via POST with `grant_type=client_credentials` and `scope` (if set) as the `scope` form parameter per RFC 6749 §4.4.2. Stores access token in `self._token` (in-memory only, never persisted). Records `self._token_expiry` — see §2.6 for fallback. On 401 responses during `discover()` or `fetch()`, see §2.6 reactive refresh.
- For API key / Bearer / Basic: sets `self._authenticated = True` immediately.
- Returns `bool`.

**`discover()`**
1. Calls `_ensure_authenticated()`.
2. Builds the request URL from `base_url + endpoint_path`.
3. Appends `since_field` query parameter if `last_sync_cursor` is set. `last_sync_cursor` for `since_field`-based sync stores ISO 8601 UTC (e.g., `"2026-04-16T00:00:00Z"`); for `pagination_style: "cursor"` sync, stores the vendor-provided opaque next-token string.
4. Paginates according to `pagination_style` using `pagination_params` keys (see §3.1 sub-table). For `none`, fetches one page only.
5. **`max_records` guard:** stops and logs `WARNING: "Discovery capped at {max_records} records — check pagination_style config"` when total count reaches `max_records` (default `10_000`).
6. For each item in each page response, emits one `DiscoveredRecord`:
   - `source_path` = value at `record_id_field` JSON path
   - `filename` = synthesized from response metadata (e.g., `"record_{id}.json"`)
   - `mime_type` = hint derived from `response_format`. Discovery-stage hint only; authoritative `mime_type` is set on `FetchedDocument` at fetch time.
7. After all pages consumed (or `max_records` hit), updates `data_sources.last_sync_cursor` and `last_sync_at` **only on full successful completion** (see §2.9).
8. Returns `list[DiscoveredRecord]`.

**`fetch(record: DiscoveredRecord)`**
1. Calls `_ensure_authenticated()`.
2. Constructs fetch URL: absolute `source_path` used directly; otherwise appends to `base_url`.
3. GETs the record through the retry utility (§2.5). Uses per-request timeout (§2.5). Response size is checked against `max_response_bytes` (§2.8) before reading body into memory.
4. Returns `FetchedDocument` with `content = response_body_bytes` and `mime_type` from `response_format`.

**`health_check()`**
1. Calls `_ensure_authenticated()`.
2. Sends `HEAD` to `base_url` through the retry utility (§2.5) — 429s on `health_check` are retried per policy. Per-request timeout (§2.5) applies.
3. **405 fallback:** if `405 Method Not Allowed`, retries immediately with `GET`. This fallback is for the 405 specifically and does NOT consume retry budget.
4. Records latency.
5. Returns `HealthCheckResult`.

### 2.4 OdbcConnector

**Identifier validation — SQL injection guard**

`{schema_name}`, `{table_name}`, `{pk_column}`, `{modified_column}` are interpolated into SQL as identifiers — bind parameters cannot bind identifiers. Validation rule: `^[A-Za-z_][A-Za-z0-9_]*$` applied via Pydantic `@field_validator` at model instantiation (see §3.2). Defense-in-depth: re-applied at query construction before interpolation.

**Error-message scrubbing — connection-string leakage**

`pyodbc` exceptions routinely include the DSN in the message. Scrubbing strategy: parse `connection_string` into DSN components (extract `USER`/`UID`, `PWD`/`PASSWORD`, server/host values via `re.split`) and scrub each component independently from the exception message, in addition to scrubbing the full connection string. The full-string replace is belt-and-suspenders; component scrubbing catches partial DSN leakage (e.g., only the password appearing in an auth error). Only the scrubbed message is exposed to callers, API responses, UI, and log lines at INFO/WARNING. Raw exceptions are retained only at DEBUG server-side.

**`authenticate()`**
- Calls `pyodbc.connect(connection_string)` (or sqlite3 adapter in tests). Stores `self._conn`.
- On failure: scrubs connection_string components from exception before re-raising.

**`discover()`**
1. Calls `_ensure_authenticated()`.
2. Builds table reference: `{schema_name}.{table_name}` if set, else `{table_name}`. Both components validated.
3. If `modified_column` and `last_sync_cursor` are set: `SELECT {pk_column}, {modified_column} FROM {table_ref} WHERE {modified_column} > ? ORDER BY {modified_column}` with `last_sync_cursor` as bind parameter.
4. If either is None: full table scan.
5. Emits one `DiscoveredRecord` per row: `source_path = "{table_name}/{pk_value}"`, `filename = "{table_name}_{pk_value}.json"`, `mime_type = "application/json"`.
6. Updates cursor **only on full successful completion** (see §2.9).
7. Returns `list[DiscoveredRecord]`.

**`fetch(record: DiscoveredRecord)`**
1. Calls `_ensure_authenticated()`.
2. Parses `source_path` for table name and PK value.
3. Executes `SELECT * FROM {table_ref} WHERE {pk_column} = ?` (bound parameter).
4. Serializes row to JSON bytes via `json.dumps(dict(row))`.
5. **Row size guard:** if `len(json_bytes) > max_row_bytes` (default 10MB), logs `WARNING: "Row {source_path} exceeds max_row_bytes; record marked failed"` and raises to the sync runner as a failed record. The sync runner's partial-failure semantics (§2.9) apply — cursor not advanced. This mirrors the REST `max_response_bytes` guard (§2.8).
6. Returns `FetchedDocument` with `content = json_bytes`, `mime_type = "application/json"`.

**`health_check()`**
1. Calls `_ensure_authenticated()`.
2. Executes `SELECT 1`.
3. Returns `HealthCheckResult`.

**`close()`** — Closes `self._conn` if open.

### 2.5 429 retry policy and per-request timeout

Implemented in `connectors/retry.py`. Used by all HTTP-based connectors. Must not be re-implemented per connector.

**Per-request timeout:** All HTTP requests are issued with a per-request timeout of 30 seconds (connect + read combined, as `httpx.Timeout(30.0)`). A timeout error is non-retriable — raised immediately to the caller without consuming the 429 retry budget. Timeout is distinct from the 429 retry loop.

**On 429 Too Many Requests:**
- **Max attempts:** 3 (initial + 2 retries)
- **Base delay:** 1s, doubled each attempt (1s → 2s → 4s)
- **Jitter:** ±20% random jitter on each delay
- **Max total wait:** 30 seconds — if next retry exceeds ceiling, raise immediately
- **`Retry-After` header:** if present, use its value as delay, subject to 30s ceiling
- **Non-retriable:** 4xx other than 429, 5xx, and timeout — all raised immediately. 5xx is non-retriable in-process because sync runs are idempotent; a transient failure is absorbed by the next scheduled run.

**Test-connection path:** The `test-connection` endpoint (§2.7) bypasses the retry utility entirely. Any 429 or transient error during test-connection raises immediately. Rationale: the admin is waiting in the wizard for instant feedback; the "fail fast" UX is correct here, and this resolves the §2.7 10s timeout / §2.5 30s retry ceiling conflict — the retry loop cannot exceed the test-connection budget if it never runs.

### 2.6 OAuth2 token refresh

**Proactive refresh:** `_ensure_authenticated()` checks `self._token_expiry`. If expired or within 60 seconds of expiry, re-authenticates transparently.

**`expires_in` fallback:** If token response omits `expires_in`, default to 3600s and log `WARNING`. If `expires_in` is zero or negative, raise `ValueError("Malformed token response: expires_in must be positive")`.

**Reactive refresh on 401 — OAuth2 only:** If `discover()` or `fetch()` receives `401 Unauthorized` AND `auth_method == "oauth2"`: invalidate `self._token`, set `self._authenticated = False`, call `_ensure_authenticated()`, retry the request once. A second 401 raises. **For all other auth methods** (`api_key`, `bearer`, `basic`), a 401 raises immediately — there is no credential refresh path. The admin must update the credential.

**Token storage:** In-memory instance variables only. Never written to the database or logs.

### 2.7 `test-connection` endpoint behavior

`POST /datasources/test-connection` for `rest_api` and `odbc`:

1. Instantiate connector from request body. Credentials are NOT persisted.
2. Call `authenticate()`.
3. Call `health_check()` — **bypasses the retry utility** (§2.5); any error raises immediately.
4. Call `close()`.
5. Return `TestConnectionResponse(success=True/False, message=..., latency_ms=...)`.

**Timeout:** Entire sequence completes within 10 seconds. Exceeded: return `TestConnectionResponse(success=False, message="Connection timed out after 10s")`.

**Error exposure:** Returned error messages MUST NOT contain credential values. For ODBC, apply §2.4 component scrubbing. For REST, strip `api_key`, `token`, `client_secret`, `password` from any exception message.

The 10s timeout does not conflict with §2.5's 30s retry ceiling because test-connection bypasses the retry utility entirely.

### 2.8 Response size limit

REST responses exceeding `max_response_bytes` (default 50MB) are refused before the body is fully read. Implementation: use `httpx` streaming; check `Content-Length` header first; if absent, read in chunks and abort when cumulative size exceeds limit. On limit hit: log `WARNING: "Response for {source_path} exceeds max_response_bytes"` and report the record to the sync runner as failed. Cursor is not advanced (§2.9).

**Scope:** This limit is per-fetch. Aggregate sync run size is bounded by `max_records × max_response_bytes` (worst case: 10,000 × 50MB = 500GB across a full run). Aggregate limiting is a plan-level concern (Celery task timeouts).

### 2.9 Cursor semantics — partial sync failure

`last_sync_cursor` and `last_sync_at` advance **only after full successful completion** of a sync run. If any `fetch()` fails mid-run, the cursor is not advanced. The next run re-discovers from the last known good cursor. Enforced at the sync runner level (`ingestion/tasks.py`).

---

## 3. Config Schemas

### 3.1 `RestApiConfig`

```python
class RestApiConfig(BaseModel):
    connector_type: Literal["rest_api"]
    base_url: str
    endpoint_path: str

    auth_method: Literal["api_key", "bearer", "oauth2", "basic", "none"]

    # api_key auth
    api_key: str | None = None                  # credential — masked in UI, omitted from GET responses
    key_header: str = "X-API-Key"
    key_location: Literal["header", "query"] = "header"

    # bearer auth
    token: str | None = None                    # credential — masked in UI, omitted from GET responses

    # oauth2 auth
    token_url: str | None = None
    client_id: str | None = None
    client_secret: str | None = None           # credential — masked in UI, omitted from GET responses
    scope: str | None = None                   # sent as 'scope' form param per RFC 6749 §4.4.2

    # basic auth
    username: str | None = None
    password: str | None = None                # credential — masked in UI, omitted from GET responses

    # pagination
    pagination_style: Literal["page", "offset", "cursor", "none"] = "none"
    pagination_params: dict = {}
    # Required keys per pagination_style:
    #   "page"   → {"page_param": "page", "size_param": "page_size"}
    #   "offset" → {"offset_param": "offset", "limit_param": "limit"}
    #   "cursor" → {"cursor_param": "next_token", "cursor_response_path": "meta.next"}
    #              cursor_response_path is dot-notation path into the JSON response envelope
    #   "none"   → {} (ignored)
    # NOTE: "cursor" pagination_style requires response_format == "json".
    # "page" and "offset" use query-string params only — compatible with all response formats.
    record_id_field: str = "id"
    since_field: str | None = None
    # since_field cursor format:
    #   time-based sync  → ISO 8601 UTC string (e.g., "2026-04-16T00:00:00Z")
    #   cursor-based sync → vendor-provided opaque token string

    # response format
    response_format: Literal["json", "xml", "csv"] = "json"
    # "json": mime_type = "application/json"
    # "xml":  mime_type = "application/xml"
    # "csv":  mime_type = "text/csv"
    # Binary / multipart out of scope for v1.
    # cursor pagination_style requires json (enforced by @model_validator below).

    # limits
    max_response_bytes: int = 50 * 1024 * 1024  # 50MB per fetch
    max_records: int = 10_000

    @model_validator(mode="after")
    def validate_pagination_format_compat(self) -> "RestApiConfig":
        if self.pagination_style == "cursor" and self.response_format != "json":
            raise ValueError(
                "pagination_style='cursor' requires response_format='json'. "
                "CSV and XML responses have no JSON envelope to read the cursor from. "
                "Use pagination_style='page' or 'offset' for non-JSON endpoints."
            )
        return self
```

### 3.2 `ODBCConfig`

```python
class ODBCConfig(BaseModel):
    connector_type: Literal["odbc"]
    connection_string: str      # CREDENTIAL — masked in UI, omitted from GET responses, never logged
                                # JDBC DSNs frequently embed credentials inline (user=foo;password=bar).
                                # Frontend code MUST include comment: # CREDENTIAL — do not display

    schema_name: str | None = None
    table_name: str
    pk_column: str
    modified_column: str | None = None
    max_row_bytes: int = 10 * 1024 * 1024  # 10MB per row; mirrors REST max_response_bytes

    @field_validator("schema_name", "table_name", "pk_column", "modified_column", mode="before")
    @classmethod
    def validate_identifier(cls, v: str | None) -> str | None:
        """Prevent SQL injection via identifier interpolation.
        Bind parameters cannot bind SQL identifiers. Allowlist regex enforced.
        """
        if v is None:
            return v
        import re
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", v):
            raise ValueError(
                f"Identifier '{v}' contains invalid characters. "
                "Only letters, digits, and underscores are allowed, "
                "starting with a letter or underscore."
            )
        return v
```

### 3.3 `ConnectorConfig` discriminated union

```python
# schemas/connectors/__init__.py
from typing import Annotated, Union
from pydantic import Field

ConnectorConfig = Annotated[
    Union[RestApiConfig, ODBCConfig],
    Field(discriminator="connector_type")
]
```

All router endpoints that accept connector configuration use `ConnectorConfig`. Pydantic dispatches validation to the correct model and returns field-level errors.

### 3.4 UI masking and API write-only requirement

**Write-only fields:** `api_key`, `token`, `client_secret`, `password` (RestApiConfig) and `connection_string` (ODBCConfig).

**In the wizard:** displayed as `••••••••` after save. No reveal button.

**In GET API responses:** omitted entirely — not masked, not returned as null. A city IT admin must re-enter credentials to update them.

**In frontend code:** `connection_string` MUST carry an inline comment: `// CREDENTIAL: treat as api_key — never display, log, or echo`.

---

## 4. Database Migration

One migration covers REST, ODBC, and future IMAP incremental sync. After `upgrade()`, existing rows retain NULL; existing connectors trigger a full re-sync on first run.

### 4.1 Alembic migration (upgrade + downgrade)

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

Required test cases:
- `test_api_key_header`, `test_api_key_query`
- `test_bearer_auth`
- `test_oauth2_auth` — token exchange, in-memory storage, proactive refresh on expiry
- `test_oauth2_reactive_401_refresh` — 401 triggers one re-auth + retry; second 401 raises
- `test_oauth2_reactive_401_non_oauth_raises` — `auth_method="api_key"` 401 raises immediately (no refresh)
- `test_oauth2_expires_in_missing` — defaults to 3600, logs WARNING
- `test_oauth2_expires_in_zero` — raises ValueError
- `test_basic_auth`
- `test_discover_pagination_page`, `test_discover_pagination_cursor`, `test_discover_pagination_offset`
- `test_discover_max_records_cap` — WARNING logged, stops at `max_records`
- `test_discover_429_retry` — retries with backoff; `Retry-After` respected
- `test_discover_empty_page_terminates`
- `test_fetch_absolute_url`, `test_fetch_relative_id`
- `test_fetch_xml_response_format` — `FetchedDocument.mime_type == "application/xml"`
- `test_fetch_csv_response_format` — `FetchedDocument.mime_type == "text/csv"`
- `test_fetch_response_too_large` — record reported as failed, cursor not advanced
- `test_health_check_head_success`
- `test_health_check_head_405_falls_back_to_get`
- `test_health_check_429_retried`
- `test_cursor_pagination_requires_json` — `pagination_style="cursor"` + `response_format="csv"` raises at config instantiation
- `test_per_request_timeout` — slow endpoint triggers timeout; raised immediately, not retried
- `test_test_connection_bypasses_retry` — 429 during test-connection raises immediately (no backoff)
- `test_connection_safety` — calls test-connection; asserts:
  1. `len(audit_entries) >= 1` — at least one `AuditLog` entry written (vacuous pass on empty list is a bug)
  2. `data_sources.connection_config` byte-for-byte unchanged in DB
  3. No credential value (`api_key`, `token`, `client_secret`, `password`) appears as a substring of any string value at any depth in any `AuditLog.details` JSONB — recursive walk required; flat `.get()` check explicitly prohibited

### 5.2 `test_odbc_connector.py` — using sqlite3 adapter

Required test cases:
- `test_identifier_validation_valid`
- `test_identifier_validation_injection` — `"foo; DROP TABLE"` raises ValueError at instantiation
- `test_identifier_validation_schema_dot_table`
- `test_discover_full_scan`
- `test_discover_incremental`
- `test_discover_with_schema_name`
- `test_fetch_row` — correct JSON serialization
- `test_fetch_row_too_large` — row exceeds `max_row_bytes`; reported as failed, cursor not advanced
- `test_health_check`
- `test_error_scrubbing` — pyodbc exception containing connection_string and DSN components is scrubbed before propagation; neither the full string nor any extracted credential component appears in the raised message
- `test_connection_safety` — same as REST variant:
  1. `len(audit_entries) >= 1`
  2. `connection_config` unchanged in DB
  3. `connection_string` value and DSN credential components do not appear at any depth in `AuditLog.details` JSONB (recursive walk, shared helper with REST variant)

### 5.3 Integration tests — `test_ingestion_tasks.py`

**Cursor semantics:**

`test_partial_sync_cursor_not_advanced`:
1. `discover()` returns N records.
2. Simulate `fetch()` failure on record `N/2`.
3. Assert `data_sources.last_sync_cursor` equals pre-run value.
4. Assert records `N/2 + 1` through `N` are not marked as ingested.

**Connection lifecycle:**

`test_close_called_on_success` — sync runner calls `close()` in `finally` after successful run.
`test_close_called_on_failure` — sync runner calls `close()` in `finally` even when `fetch()` raises.

These tests belong in `test_ingestion_tasks.py`, not the connector unit tests, because the `close()` contract is enforced by the sync runner, not the connector — same logic that put `test_partial_sync_cursor_not_advanced` here.

---

## 6. Wiring Checklist

- [ ] `backend/app/connectors/base.py` — add default no-op `close()` method so sync runner can call `close()` on existing connectors (`file_system`, `imap_email`, `manual_drop`) without `AttributeError`
- [ ] `backend/app/connectors/retry.py` — shared HTTP retry utility (§2.5); includes per-request timeout; test-connection bypass documented
- [ ] `backend/tests/test_retry.py` — unit tests: backoff, jitter, Retry-After, ceiling, timeout behavior, test-connection bypass
- [ ] `backend/app/connectors/rest_api.py` — RestApiConnector
- [ ] `backend/app/connectors/odbc.py` — OdbcConnector (identifier validation, component scrubbing, row size guard, close())
- [ ] `backend/app/connectors/__init__.py` — register both types in connector factory
- [ ] `backend/app/schemas/connectors/__init__.py` — `ConnectorConfig` discriminated union (§3.3)
- [ ] `backend/app/schemas/connectors/rest_api.py` — RestApiConfig (with `@model_validator`)
- [ ] `backend/app/schemas/connectors/odbc.py` — ODBCConfig (with `@field_validator`)
- [ ] `backend/app/datasources/router.py` — extend `test-connection` per §2.7 (bypasses retry, 10s timeout, credential scrubbing)
- [ ] `backend/alembic/versions/` — migration with `upgrade()` + `downgrade()` (§4.1)
- [ ] `backend/app/ingestion/tasks.py` — cursor write only on full success; `close()` in `finally`
- [ ] `frontend/` — wizard Step 2 branching; mask `token`, `api_key`, `client_secret`, `password`, `connection_string`; omit all from GET serialization; inline `# CREDENTIAL` comment on `connection_string`
- [ ] `backend/tests/test_rest_connector.py`
- [ ] `backend/tests/test_odbc_connector.py`
- [ ] `backend/tests/test_ingestion_tasks.py` — cursor test + close() lifecycle tests (§5.3)
- [ ] `docs/UNIFIED-SPEC.md` — update §11.4 REST API and ODBC/JDBC from [PLANNED] to [IMPLEMENTED]
- [ ] `CHANGELOG.md` — entry for connector expansion
