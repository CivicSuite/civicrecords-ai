# T2B Schema Audit — Sensitive Field Sweep

Date: 2026-04-20
Scope: Every user-visible response schema in `backend/app/schemas/` and inline router schemas.
Audited by: dev (initial sweep); required auditor verification under CLAUDE.md Hard Rule 1.

Sensitive field list: `connection_config`, `api_key`, `token`, `password`, `client_secret`,
`database_url`, `connection_string`, `client_secret`.

---

## Findings

### FIXED — `DataSourceRead.connection_config` exposed to STAFF

**File:** `backend/app/schemas/document.py`
**Route:** `GET /datasources/` (`require_role(UserRole.STAFF)`)
**Field:** `connection_config: dict`
**Risk:** Any authenticated STAFF user could read the full connection config for every
data source, including stored credentials inside the JSONB blob (REST API keys, bearer
tokens, OAuth client secrets, ODBC connection strings).
**Fix:** `connection_config` removed from `DataSourceRead`. New `DataSourceAdminRead`
subclass adds it back; used only by admin-gated `POST /datasources/` and
`PATCH /datasources/{id}`.
**Status:** FIXED in this PR.

### FIXED (transitively) — Connector credential fields in `connection_config` JSONB

**Files:**
- `backend/app/schemas/connectors/rest_api.py` — `api_key`, `token`, `client_secret`, `password`
- `backend/app/schemas/connectors/odbc.py` — `connection_string`

**Risk:** These fields are input schemas that get serialized as JSONB into
`DataSource.connection_config`. They were reachable by STAFF via the `DataSourceRead`
exposure above.
**Fix:** Covered by the `DataSourceRead` redaction above. The connector config schemas
themselves are input-only; they are not used as response schemas.
**Status:** FIXED transitively by the `DataSourceRead` fix.

---

## Clean — No Action Required

| Schema file | Fields reviewed | Finding |
|---|---|---|
| `schemas/document.py` — `DocumentRead` | All fields | None — no credentials |
| `schemas/document.py` — `DocumentChunkRead` | `token_count` | Chunk word-count integer, not a credential |
| `schemas/service_account.py` — `ServiceAccountRead` | All fields | None — `api_key_hash` not exposed, hash not returned |
| `schemas/service_account.py` — `ServiceAccountCreated` | `api_key` | By design: shown once on admin-only `POST /service-accounts/`. DB stores `api_key_hash` only. Never returned on GET. Acceptable show-once pattern. |
| `schemas/analytics.py` | All fields | None |
| `schemas/audit.py` | All fields | None |
| `schemas/city_profile.py` | All fields | None |
| `schemas/department.py` | All fields | None |
| `schemas/exemption.py` | All fields | None |
| `schemas/fee_schedule.py` | All fields | None |
| `schemas/model_registry.py` | All fields | None |
| `schemas/notifications.py` | All fields | None |
| `schemas/request.py` | All fields | None |
| `schemas/search.py` | All fields | None |
| `schemas/sync_failure.py` | All fields | None |
| `schemas/user.py` | All fields | None — `UserSelfUpdate` blocks role/dept writes; no credential fields in UserRead |
| `schemas/connectors/rest_api.py` | Input schema only | Credential fields present but never used as response schema |
| `schemas/connectors/odbc.py` | Input schema only | `connection_string` present but never used as response schema |

---

## Out of Scope for T2B (documented, not deferred without tracking)

- **At-rest encryption of `data_sources.connection_config`:** DB, pg_dump, snapshot, and
  Postgres superuser access still exposes plaintext credentials. This is Tier 6 in the
  remediation plan (`docs/REMEDIATION-PLAN-2026-04-19.md`). ENG-001 must not be marked
  fully closed until Tier 6 lands.
- **T2B closure note:** Runtime exposure of `connection_config` to non-admin users: **CLOSED**.
  Storage exposure (at rest in DB): **OPEN — tracked in Tier 6**.
