# Changelog

All notable changes to CivicRecords AI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Post-v1.1.0 commits on `master`. No version bump yet.

### Added
- **GitHub Actions CI workflow (PR 0 of 2026-04-19 remediation plan):** `.github/workflows/ci.yml` runs pytest via `docker compose` (matching AGENTS.md Hard Rule 1a auditor commands exactly) and the frontend vitest suite + production build on every push and pull request to `master`. Includes a collected-vs-passed cross-check that catches the specific failure mode documented in CLAUDE.md Hard Rule 1e ("423 tests claimed, 278 actual") by failing the job on any test skip, xfail, error, or silent early exit. Workflow is hermetic — `.env` is synthesized per-run with `openssl rand -hex 32` for `JWT_SECRET`; no secrets live in the workflow or in Actions secrets. Ollama is skipped via `--no-deps` because tests mock it. See `.github/workflows/README.md` for the full rationale and local reproduction recipe.

### Fixed
- **`/api/` prefix missing in `useSyncNow` and `FailedRecordsPanel` (`f24a3a7`, 2026-04-18):** Both hooks called `fetch('/datasources/...')` without the `/api/` prefix, routing to nginx's static handler instead of the backend — causing 405 errors on Sync Now trigger and all FailedRecordsPanel actions in production Docker. Migrated to `apiFetch` (with JWT token) and correct `/api/datasources/...` paths. Verified against live Docker: `POST /api/datasources/{id}/ingest` resolves to backend. 5/5 frontend tests passing.

### Changed
- **CHANGELOG, UNIFIED-SPEC, installer button URLs (`ad44a86`, 2026-04-18):** CHANGELOG entries added for commits `301c4f3`/`c433beb`/`9c1d98b`/`23f0655` and moved into `[1.1.0]` where they belong. Stale "30s ceiling" corrected to "600s ceiling (D-FAIL-12)". UNIFIED-SPEC §17 test count updated to 432; priority 9 entry (Rule 9 deliverables) added; D-PROC-1 decision record added; §18 process criteria added; §19 Verification Log added at position 0. All 4 installer buttons in `docs/index.html` corrected from `/raw/master/` to `/releases/download/v1.1.0/`.

### Fixed
- **T3A — Admin user creation path pointed at the real admin-create endpoint (2026-04-20):** The Users page create-user form was POSTing to `/api/auth/register`, the public self-service registration endpoint. Two consequences: (1) the form bypassed admin-only audit and validation paths, and (2) `UserCreate.force_staff_role` (in `backend/app/schemas/user.py`) silently downgraded any submitted role to `STAFF` — so an admin who picked `admin` or `reviewer` in the role dropdown got back a `staff` user with no error. Visible UX bug, not just code drift. Switched the create call to `POST /api/admin/users` (the admin-only endpoint that already accepts the same payload shape and honors the role faithfully via `AdminUserCreateRequest`). One-line change in `frontend/src/pages/Users.tsx`.

  **Accessibility fix in the same file (in-scope cleanup, found while writing the component test):** the three create-form labels (`Full Name`, `Email`, `Password`) were bare `<label>` elements with no `htmlFor` attribute and not wrapping their `<Input>`. Screen readers and keyboard users couldn't activate inputs via the label, and Testing Library's `getByLabelText` couldn't find the association at all. Added `htmlFor`/`id` pairs (`create-user-fullname`, `create-user-email`, `create-user-password`). Browser-verified: clicking each label now focuses the corresponding input. The edit-form labels have the same pre-existing gap; left for a follow-up to keep this PR scoped to T3A.

  **Tests added:**
  - `frontend/src/pages/Users.test.tsx` — vitest + Testing Library component tests that open the create dialog, fill the form, submit, and assert via a stubbed `window.fetch` that the request URL is `/admin/users` (and explicitly NOT `/auth/register`). The role-preservation test pins the actual T3A regression by **selecting `Admin` from the role dropdown** (not the default `read_only`) before submitting and asserting the captured request body carries `role: "admin"` — directly exercising the path that previously got silently downgraded to `staff` through `/auth/register`.

  **Browser QA (this PR):** desktop (1440x900) and mobile (375x812) viewports of the empty state, the create dialog, and the error state captured. Form submit captured the literal request URL `/api/admin/users` with the correct payload. Error path shows the backend `detail` in the dialog alert with the form preserved for retry. Console-warning class noted: pre-existing React `forwardRef` warnings on `Button` inside Dialog primitives — fires project-wide, not introduced or worsened by this change. Out-of-T3A-scope items flagged: SelectValue placeholder display, sidebar collapse on mobile, button-component `forwardRef` migration, edit-form label associations.

  **Out of T3A scope (deliberate, deferred to follow-up):** public `/api/auth/register` is still exposed without rate limiting; that's a separate security hardening item, not part of "fix admin user creation path."

### Security
- **T2C — Bootstrap and connector surface hardening (2026-04-20):** Two distinct hardening passes that ride together because the plan grouped them.

  **(1) `FIRST_ADMIN_PASSWORD` startup validation.** The app previously had `JWT_SECRET` startup validation but no equivalent for `FIRST_ADMIN_PASSWORD`. A user who copied `.env.example` to `.env` and started the stack would create the first admin account with the literal placeholder string `CHANGE-ME-on-first-login` — operational, deployable, and trivially compromisable. New `Settings.check_first_admin_password` model-validator in `backend/app/config.py` rejects: the `.env.example` placeholder, the default `"CHANGE-ME"`, an empty value, anything shorter than 12 characters, and a small embedded blocklist of common defaults (`admin`, `admin123`, `password`, `letmein`, `Welcome1`, etc.). Behaves like the existing JWT validator: bypassed only when `testing=True`. Both `install.sh` (Linux/macOS) and `install.ps1` (Windows) now generate a 32-hex-char admin password on fresh install and substitute it into `.env`, then print it once for the operator to capture; this avoids both the placeholder failure mode and the shell/.env metacharacter hazards of mixed-symbol generators. `.env.example` updated with explicit instructions and a manual `openssl rand -base64 24` recipe.

  **(2) SSRF/target-validator for connector URLs.** New module `backend/app/security/host_validator.py` rejects admin-supplied connector destinations that point at sensitive internal ranges. Wired into `RestApiConfig.base_url` and `RestApiConfig.token_url` (REST connector) and `ODBCConfig.connection_string` (ODBC connector) as Pydantic field validators — rejection happens at schema-validation time, before any HTTP client or pyodbc dial.

  **Blocked targets (reject by default):**
  - `127.0.0.0/8` — loopback IPv4
  - `169.254.0.0/16` — link-local / cloud IMDS endpoints
  - `::1/128` — loopback IPv6
  - `0.0.0.0` — wildcard
  - `localhost` — case-insensitive hostname
  - `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16` — RFC1918

  **Override:** new `CONNECTOR_HOST_ALLOWLIST` setting (CSV in env, list in code) — exact-match hostnames or IPs only. No wildcards, no "disable all" flag. Auditor instruction: keep this narrow.

  **ODBC fail-closed behavior:** the parser extracts the host from `Server=`, `Host=`, or `Data Source=` (case-insensitive, supports `host,port` / `host:port` / `{braced}` forms). If no parseable host field is found, validation **raises** rather than silently passing — explicit auditor instruction. This means DSN-only connection strings (`DSN=name`) are rejected. Operators who need DSN-based connections must refactor to `Server=...` form or rely on a future enhancement (out of scope for T2C).

  **Unit tests added:**
  - `backend/tests/test_host_validator.py` — parametrized coverage of every blocked range, boundary-adjacent public ranges (so the masks aren't accidentally widened), hostname case-insensitivity, ODBC parser variants (SQL Server `host,port` style, PostgreSQL `host:port`, braced values, `Data Source` alias), allowlist exact-match and case-insensitivity, allowlist rejection of wildcard literals, and fail-closed on empty/ambiguous input.
  - `backend/tests/test_config_validation.py` — placeholder, blocklist, length, and valid-strong-password cases for `FIRST_ADMIN_PASSWORD`; testing-mode bypass; CSV parsing of `CONNECTOR_HOST_ALLOWLIST` (native list, CSV string, whitespace and empty-entry handling); a tripwire test (`test_env_example_placeholder_value_is_in_blocklist_inline`) that fails red if the `.env.example` placeholder string drifts out of sync with the validator blocklist.

  **Integration tests added (the T2C plan item #4 merge gate):**
  - `backend/tests/test_bootstrap_integration.py` — spawns a fresh Python subprocess with the `.env.example` placeholder for `FIRST_ADMIN_PASSWORD` and asserts the same import-time `Settings()` path that runs when `docker compose up` boots the api container exits non-zero with `FIRST_ADMIN_PASSWORD` in the error. Includes a control test that the same subprocess path with a strong password exits 0 (so a broken Python install can't make the failure test pass for the wrong reason), plus a length-check case and a blocklist case.
  - `.github/workflows/ci.yml` — new `bootstrap-failure` CI job that runs the literal `docker compose run --rm --no-deps api python -c "from app.config import Settings; Settings()"` against the real api image with the `.env.example` placeholder password, and asserts non-zero exit + `FIRST_ADMIN_PASSWORD` in stderr. A second step inside the same job verifies the same path succeeds with a strong password (control). This is the closest possible mirror of the plan's "fresh `docker compose up` fails to start" requirement that fits inside the existing CI architecture.

  **Existing-test cleanup (in scope, follows directly from the new validator):** four existing test files used `connection_string="DSN=test"` as schema-fixture data. With the new ODBC fail-closed rule those instances would raise. Updated to `connection_string="Server=db.example.gov;Database=test"` — functionally equivalent for unit-test purposes (real ODBC connection is mocked via `pyodbc` patching) and keeps the test intent intact. Files: `test_connector_schemas.py`, `test_odbc_connector.py`. The `_scrub_error` test in `test_datasources_router_tc.py` uses a DSN-shaped string as test input to a sanitizer and was left unchanged (not an ODBCConfig instance).

- **T2B — `DataSourceRead.connection_config` credential exposure closed (2026-04-20):** `GET /datasources/` was accessible to all STAFF-and-above users and returned the full `DataSourceRead` schema, which included `connection_config: dict`. That JSONB blob contains every credential stored for the data source — REST API keys, bearer tokens, OAuth `client_secret`, ODBC `connection_string`, IMAP passwords — all readable by any authenticated staff member, not just admins who manage the sources.

  **The fix:** `connection_config` removed from `DataSourceRead`. A new `DataSourceAdminRead` subclass adds it back; `DataSourceAdminRead` is used only by `POST /datasources/` and `PATCH /datasources/{id}`, both of which are already gated at `require_role(UserRole.ADMIN)`. `GET /datasources/` continues to use `DataSourceRead` (redacted) for all callers including admins.

  **Schema audit checklist:** `docs/T2B-SCHEMA-AUDIT-2026-04-20.md` — every response schema in `backend/app/schemas/` swept for credentials, connection strings, tokens, OAuth client secrets, internal-only fields. One additional finding (`ServiceAccountCreated.api_key`) confirmed as intentional show-once pattern (admin-only POST, DB stores hash only, never returned on GET). Connector config schemas (`RestApiConfig`, `ODBCConfig`) confirmed as input-only; their credential fields are transitively covered by the `DataSourceRead` redaction.

  **Tests added** in `backend/tests/test_datasources.py` (4 new, zero skips):
  - `test_staff_list_datasources_no_connection_config` — STAFF GET `/datasources/` → all sensitive fields absent from every item in the response
  - `test_admin_list_datasources_no_connection_config` — ADMIN GET `/datasources/` → `connection_config` absent (redacted shape applies to all callers on list)
  - `test_admin_create_datasource_returns_connection_config` — ADMIN POST `/datasources/` → `connection_config` present and matches submitted config
  - `test_admin_update_datasource_returns_connection_config` — ADMIN PATCH `/datasources/{id}` → `connection_config` present and matches updated config

  **Scope limit (T2B closure note):** Runtime exposure of `connection_config` to non-admin users: **CLOSED**. Storage exposure (plaintext in DB, accessible via pg_dump, snapshots, Postgres superuser): **OPEN — tracked in Tier 6 of the remediation plan**. ENG-001 must not be marked fully closed until Tier 6 (at-rest encryption) lands.

- **Info-leak follow-up — 404-vs-403 status code disclosure closed across the dept-scoped surface (2026-04-20):** Started as a narrow fix for the two child-before-parent handlers filed in `docs/FINDING-2026-04-19-info-leak-child-before-parent.md`. During the fix a codebase-wide audit surfaced the **same 404-vs-403 disclosure at the parent level** — every handler that loads a RecordsRequest or Document by path-param ID and then raises 403 via `require_department_scope` had the identical status-code side channel. Scope was expanded to cover all of it. Owner directive 2026-04-20: "wrong move" to leave the broader pattern for a future PR.

  **The pattern:** fake `request_id` → 404 "Request not found"; real `request_id` in another dept → 403. An authenticated cross-department caller could distinguish a leaked/guessed UUID's status via the difference. Same shape for documents, letters, flags.

  **The fix — `require_department_or_404` helper** added in `backend/app/auth/dependencies.py`. Same fail-closed rules as `require_department_scope` but raises **404** (not 403) on denial, with a configurable detail string. The external response is identical to "resource does not exist", closing the status-code side channel.

  **Coverage after this PR (404-unified via `require_department_or_404`):**
  - `backend/app/requests/router.py` — 17 call sites (GET/PATCH `/{id}`, attached documents, workflow verbs, fees, response-letter, timeline, messages, fee-waiver review)
  - `backend/app/documents/router.py` — 2 call sites (GET `/{id}`, GET `/{id}/chunks`)
  - `backend/app/exemptions/router.py` — 2 call sites (POST `/scan/{request_id}`, GET `/flags/{request_id}`)
  - `backend/app/exemptions/router.py::review_flag` — 404-unified inline via `has_department_access` (because the flag must load first — no call site to swap)

  **The two original child-before-parent cases** remain fixed as filed:
  - `update_response_letter` — reorder (parent-load + dept-check before letter lookup), now using `require_department_or_404`
  - `review_flag` — inline 404-unification with `has_department_access`; also closes a separate pre-existing fail-open where the old code guarded the dept check behind `if req:` and silently skipped it if the flag referenced a missing parent

  **Intentionally left at 403** (semantic denial, no info-leak):
  - List endpoints (`GET /documents/`, `GET /analytics/operational`, request list filters) — no specific ID in path; null-user-dept still raises 403 inline
  - `/city-profile` — intentionally global singleton per T2A design decision, admin-write only
  - Role-gate 403s from `require_role(...)` — unrelated to dept scoping

  **New helpers in `backend/app/auth/dependencies.py`:**
  - `has_department_access(user, resource_department_id) -> bool` — non-raising variant, same rules
  - `require_department_or_404(user, resource_department_id, detail) -> None` — fail-closed with 404 disclosure-closed denial

  **Tests — cross-dept assertions flipped 403 → 404 where appropriate:**
  - `backend/tests/test_info_leak_hardening.py` (new, 6 tests, zero skips): placeholder letter_id cross-dept → 404, real letter_id cross-dept → 404, admin bypass on letter PATCH → 200, placeholder flag_id → 404, real flag cross-dept → 404 with body "Flag not found", admin bypass on flag → 200
  - `backend/tests/test_tier2a_hardening.py`: parameterized enforcement test now asserts 404 (was 403) across 25 cases; individual documents/timeline/messages cross-dept tests flipped; list-endpoint null-user-dept tests stay 403 (unchanged)
  - `backend/tests/test_department_scoping.py`: `test_staff_gets_request_in_other_department_404` (renamed from `_403`); `test_reviewer_cannot_approve_other_department` assertion flipped to 404

  **`docs/FINDING-2026-04-19-info-leak-child-before-parent.md`** rewritten to document the expanded scope and the two fix patterns (`require_department_or_404` for swap-compatible sites, inline `has_department_access` for `review_flag`).

  **UX tradeoff:** same-tenant users who mistype a UUID now see "Not found" for both "does not exist" and "exists in another dept." Correct from a security standpoint (GitHub, Google Drive, Dropbox all unify on 404 for authz-sensitive resources). Acceptable because cross-dept access was never a supported user path.

  **Second scope expansion — Pattern D list-endpoint fail-open, auditor-flagged 2026-04-20:** The first pass of this PR claimed "list endpoints intentionally left at 403" — that claim was false for 4 routes. `GET /requests/`, `GET /requests/stats`, `POST /search/query`, and `GET /search/export` all had the shape `if user.role != UserRole.ADMIN and user.department_id is not None:` — which silently skipped the dept filter for a null-dept non-admin, returning unscoped results. A codebase-wide sweep for this pattern (grepping `user.department_id is not None` in router handlers without a matching fail-closed branch) found exactly these 4. New helper `require_department_filter(user)` added in `backend/app/auth/dependencies.py` — returns None for admin, raises 403 for non-admin + null dept, returns `user.department_id` otherwise. All 4 call sites converted. One adjacent reorder: `execute_search` now runs the dept check BEFORE `session.add(SearchSession(...))` so a 403 does not leave an orphan SearchSession row. 4 new regression tests added (`test_list_requests_denies_non_admin_with_null_department`, `test_request_stats_denies_non_admin_with_null_department`, `test_search_query_denies_non_admin_with_null_department`, `test_search_export_denies_non_admin_with_null_department`). The "list endpoints at 403" wording in the first pass was wrong for these 4 routes; corrected here.

- **Partial Tier 2A auth/authz hardening (remediation plan §T2A — first slice, not full closure):** Covers four of the nine items in the agreed T2A scope. Explicitly **NOT closed**: apply `require_department_scope` to analytics / messages / timeline / city-profile routers, and add the parameterized cross-endpoint enforcement test. Those are tracked as follow-up PRs to complete T2A.
  - **Blocker (`ENG-002`) — role self-escalation via `PATCH /users/me` closed.** Introduced `UserSelfUpdate` schema in `backend/app/schemas/user.py`. It inherits `fastapi_users.schemas.BaseUserUpdate` but adds a `@model_validator(mode="before")` that rejects any payload containing `role` or `department_id` with HTTP 422. `backend/app/auth/router.py` now wires `fastapi_users.get_users_router(UserRead, UserSelfUpdate)` — the `/users/me` path no longer accepts privileged fields. Admin role and department changes continue to go through `/admin/users/{id}`.
  - **Blocker (`ENG-003`) — unscoped `/documents/` router closed.** `backend/app/documents/router.py` now applies department scoping on list (WHERE clause) and on GET + chunks (after-load check via the new helper). Admin bypass preserved.
  - **Critical (`ENG-006`) — fail-closed department scope helper added for `/documents/` only.** New `require_department_scope(user, resource_department_id)` in `backend/app/auth/dependencies.py`. Denies when user has no department, denies when resource has no department, denies on cross-department access. Admin bypass. Applied only to `/documents/` in this change; existing `check_department_access` (used by requests, search, analytics, messages, timeline, city-profile routers) is left unchanged to keep this PR's blast radius contained, with a deprecation note. Migration of other callers and the parameterized cross-endpoint test are the remaining items of T2A.
  - **Tests added** in `backend/tests/test_tier2a_hardening.py` (10 tests): role-escalation rejection with `{"role": "admin"}` → 422, department-id rejection with `{"department_id": uuid}` → 422, mixed payload `{"full_name": "Sneaky", "role": "admin"}` → 422, full_name-only PATCH → 200, cross-department deny for list + get + chunks, null-department user deny on list, null-department resource deny for non-admin, admin bypass.

- **Tier 2A completion (remediation plan §T2A — completes the rollout started in the prior partial PR):**
  - **Analytics:** `backend/app/analytics/router.py` — `GET /analytics/operational` now applies a fail-closed `RecordsRequest.department_id == user.department_id` predicate to every aggregate query for non-admin users. Admin bypass preserved. Non-admin with no department → 403. The by-department map is still empty pending T3.
  - **Messages + timeline:** `backend/app/requests/router.py` — the four GET/POST handlers for `/{request_id}/timeline` and `/{request_id}/messages` migrated from `check_department_access` (fail-open on null resource dept) to `require_department_scope` (fail-closed). The other four `check_department_access` call sites in this file (on the core request endpoints) are intentionally unchanged — they are outside T2A scope and tracked as a separate follow-up.
  - **City-profile:** `backend/app/city_profile/router.py` — design documented in a module docstring. Intentionally NOT department-scoped: city-profile is a per-install singleton, not department-owned data. Access model unchanged (STAFF read, ADMIN write). This closes T2A's city-profile item by decision, not by code change.
  - **Parameterized cross-endpoint enforcement test** added to `backend/tests/test_tier2a_hardening.py`: iterates 7 T2A-scoped routes (documents get/chunks, requests get/timeline/messages — both read and write) and asserts a dept-A token receives 403 on every one. Reports all failing routes in a single assertion message so new regressions surface together.
  - **Additional tests (9 new, 19 total in the file):** analytics dept filter for non-admin, analytics admin-sees-all, analytics null-dept deny, timeline/messages cross-dept deny (4 tests for GET+POST × timeline+messages), null-user-dept deny on timeline and messages, and the parameterized test.
  - **What T2A closes with this PR:** ENG-002 (role self-escalation), ENG-003 (documents scoping), ENG-006 (fail-closed helper) for the five routers named in the plan + the enforcement test. **Not closed:** migration of the four remaining `check_department_access` call sites in `requests/router.py` (core request endpoints); explicitly a follow-up, not part of T2A as scoped in the plan.

- **T2A-cleanup — remaining fail-open helper migration (follow-up beyond T2A-as-scoped):**
  - **Correction to prior entries.** The two T2A entries above state "four remaining `check_department_access` callers" and "other four call sites in this file." Both counts were wrong. Grep against the repo at that time showed **16 remaining callers in `backend/app/requests/router.py`** plus **3 additional callers in `backend/app/exemptions/router.py`** (19 total), not 4. The earlier numbers came from a truncated grep. This PR migrates all 19 and removes the helper entirely.
  - **`backend/app/requests/router.py`:** all 16 `check_department_access(user, req.department_id)` call sites swapped to `require_department_scope(user, req.department_id)`. Covers GET/PATCH `/requests/{id}`, attached-documents (POST/GET/DELETE), workflow (submit-review / ready-for-release / approve / reject), fees (GET/POST + estimate-fees + fee-waiver), and response-letter (POST/GET/PATCH). Import updated accordingly.
  - **`backend/app/exemptions/router.py`:** all 3 call sites swapped. Covers POST `/exemptions/scan/{request_id}`, GET `/exemptions/flags/{request_id}`, and PATCH `/exemptions/flags/{flag_id}`.
  - **`backend/app/auth/dependencies.py`:** `check_department_access` function **removed**. Grep-confirmed zero callers remain in `backend/app/`.
  - **Auditor follow-up — additional gap found and fixed in the same PR.** The original parameterized enforcement test missed `PATCH /requests/{id}/fee-waiver/{waiver_id}` (`review_fee_waiver`). That handler never called `check_department_access` in the first place, so the helper migration didn't touch it — but it also never had any dept-scope check, meaning a cross-department reviewer could approve/deny a fee waiver and flip `req.fee_status`. Auditor caught this on review before merge. Fix: added `require_department_scope(user, req.department_id)` in `review_fee_waiver` at `requests/router.py:860` (right after the parent request load, before the waiver load). A repo-wide grep for handlers that load `RecordsRequest` and never call `require_department_scope` is now clean (24 scoped, 0 unscoped).
  - **Parameterized cross-endpoint enforcement test** extended from 7 cases to **25 cases** in `backend/tests/test_tier2a_hardening.py`, covering every dept-scoped route including the newly-added `review_fee_waiver` PATCH. Real dept-B fee-waiver seeded via POST so the PATCH case exercises the dept check against a live waiver record, not a placeholder. One exception: PATCH `/exemptions/flags/{flag_id}` is not in the parameterized list because it requires a seeded exemption flag in dept B (the handler loads the flag before the parent request); covered by a follow-up targeted test if added. Caller token upgraded to `reviewer_token_dept_a` so workflow routes gated at REVIEWER pass the role check and reach the dept check (where 403 is the test's target).
  - **What this closes:** every `@router.*` handler in `backend/app/` that loads `RecordsRequest` now calls `require_department_scope` before any mutation or response. Grep-verified: 24/24 handlers scoped, 0/24 unscoped. The prior phrasing — "all fail-open semantics on department-scoped paths closed" — was incorrect on the first pass because `review_fee_waiver` had no scope at all, not just a fail-open one; it wasn't in the migration list and wasn't caught by the first parameterized test. Corrected here.
  - **What is NOT in scope (and is not closed by this PR):** everything in Tiers 2B, 2C, 3, 4, 5 of the remediation plan. T2A-as-scoped-in-the-plan was already complete at PR #17; this PR is strictly the helper-migration cleanup plus the fee-waiver review route the auditor flagged.

### Added
- **Department Scoping:** Department model with CRUD API, department assignment on users and data sources, department-based access control on requests
- **50-State Exemption Rules:** 180 exemption rules across 51 jurisdictions (50 states + DC), seeded from canonical state public records law database
- **Compliance Templates:** 5 seeded compliance documents (AI use disclosure, response letter disclosure, CAIA impact assessment, AI governance policy, data residency attestation)
- **Model Registry:** Admin-managed Ollama model registry with context window tracking, active model selection, and automatic budget scaling in context manager
- **Central LLM Client:** All LLM generation calls route through `app/llm/client.py` — enforces context manager budgeting, prompt injection sanitization, and model-registry context window scaling on every call. Refactored exemptions reviewer, search synthesizer, and ingestion extractor to use it
- **Notification System:** 12 notification templates aligned with all router-dispatched event types, city_name sourced from city profile for email templates, queue_notification wired into 5 status transitions
- **Users Edit/Deactivate:** PATCH /admin/users/{id} endpoint with self-demotion lockout and self-deactivation guard. Frontend edit dialog and deactivate button with confirmation
- **Search Department Filter:** Department filtering on both semantic and keyword search engines via document-source-department join chain. Department dropdown in search UI
- **Search CSV Export:** GET /search/export endpoint with authenticated download. Export button in search results
- **Fee Estimation:** POST /requests/{id}/estimate-fees — staff enters page count, system calculates from fee schedule rates
- **Fee Waivers:** FeeWaiver model with Alembic migration, create/approve/deny workflow, automatic fee_status update on approval. Waiver types: indigency, public interest, media, government, other
- **Exemption Audit History:** GET /exemptions/rules/{id}/history returns audit log entries for any rule. Timeline UI in Exemptions page
- **Exemption Rule Test Modal:** POST /exemptions/rules/{id}/test — tests regex or keyword rules against sample text with match positions. ReDoS protection via `regex` library with 2-second timeout. LLM-type rules rejected with 400
- **Sources 3-Step Wizard:** Replaced single-step add dialog with guided wizard (source type selection, connection config per type, review + test connection). POST /datasources/test-connection validates connectivity without persisting credentials
- **Dashboard Coverage Gaps:** GET /admin/coverage-gaps identifies jurisdictions without exemption rules, departments without assigned staff, and exemption categories without active rules. Warning card on dashboard when gaps > 0
- **Search Citation Rendering:** AI summary panel renders [Doc: filename, Page: N] citations as styled inline badges instead of plain text
- **Request Priority Indicators:** Priority column with colored badges (urgent/expedited/normal/low) on Requests table
- **Ingestion Retry:** POST /datasources/documents/{id}/re-ingest retries failed documents (resets to pending, queues Celery task). Progress indicator for processing items, auto-refresh while active
- **Rich Text Editor:** TipTap editor replaces plain textarea for response letter editing. Toolbar with bold, italic, underline, bullet list, ordered list. Content stored as HTML in edited_content field
- **Onboarding LLM Interview:** POST /onboarding/interview generates adaptive setup questions based on incomplete city profile fields. Chat-style UI with skip button, profile updates via PATCH /city-profile. Falls back to default questions when LLM unavailable
- **DOCX/XLSX Macro Stripping:** Parsers strip VBA macros at ZIP level before text extraction. Supports .docm and .xlsm. Stripping logged in metadata for audit
- **WCAG 44x44px Touch Targets:** min-width: 44px added alongside min-height for all interactive elements. All icon button variants enforce minimum touch target
- **P7 — Sync failures, circuit breaker, UI polish (`32ceb9c`, 2026-04-17):** Per-record failure tracking via `sync_failures` table (status: retrying/permanently_failed/dismissed/tombstone). Two-layer retry: task-level (3 retries, 30s→90s→270s, 10-min cap) + record-level (5 retries OR 7 days, N=100/T=90s per-run cap). Circuit breaker: 5 consecutive full-run failures → `sync_paused=true`; unpause sets grace threshold=2 for faster admin feedback. `health_status` computed at response time via single LEFT JOIN (circuit_open > degraded > healthy — no stored field). `sync_run_log` one row per sync run (start, end, counts). Option B SourceCard layout: colored health dot, failure counts, schedule state (manual/paused/next-run), Sync Now button, "View failures" toggle. `FailedRecordsPanel`: 5 states (loading/empty/populated/error + circuit-open banner), bulk retry-all/dismiss-all, per-row Retry/Dismiss. Sync Now polling: exponential backoff 5s→10s→20s→30s cap, 15-min timeout, elapsed time display. `useSyncNow` hook with refs for timer management. 429/Retry-After honored at `RestApiConnector` layer (capped 600s, D-FAIL-12). `IntegrityError` → `permanently_failed` without task retry (D-FAIL-10). `formatNextRun()` in wizard Step 3: `cron-parser` v4 with UTC + local time display, `data-testid=cron-preview`. Shadcn `Checkbox` replaces native input in schedule toggle. `conftest` migrated from `Base.metadata.create_all()` to `DROP SCHEMA public CASCADE` + `alembic upgrade head` subprocess (true migration parity; eliminates model/migration schema drift). 423 backend tests passing (+28 new vs. P6b); 5 frontend tests passing.
- **P6b — Cron scheduler rewrite (`c670ef1`, 2026-04-17):** `sync_schedule` (5-field cron, croniter Apache 2.0) replaces drift-prone `schedule_minutes` interval. `schedule_enabled` boolean toggle preserves the expression on pause. Scheduler trigger logic corrected to `croniter.get_next(datetime) <= now` in UTC (original `get_prev() > anchor` inverted logic would never fire). Cron validation via Pydantic `@field_validator` at API boundary rejects invalid expressions with 422 and rejects adversarial patterns (e.g. `*/1 0 * * *`) via rolling 7-day sampling (2016 ticks) with a 5-minute floor. Wizard Step 3 adds 8 schedule presets + Manual + "Schedule enabled" toggle; GET `/datasources/` computes `next_sync_at` at response time. Migration 015 adds `schedule_enabled` (default true), a `chk_sync_schedule_nonempty` constraint, 8 P7 stub columns (`consecutive_failure_count`, `last_error_message`, `last_error_at`, `sync_paused`, `sync_paused_at`, `sync_paused_reason`, `retry_batch_size`, `retry_time_limit_seconds`), and converts legacy `schedule_minutes` via a 13-entry allowlist (5→`*/5 * * * *` through 1440→`0 2 * * *`); non-allowlist values are nulled and recorded in `_migration_015_report`. 395/397 tests passing (+13 new). D-SCHED-5 three-state card display deferred to P7.
- **P6a — Idempotency contract split (`e462c7e`, 2026-04-16):** Dedup contract split by connector type. Binary connectors (UPLOAD, DIRECTORY) continue to dedup by `(source_id, file_hash)`. Structured connectors (REST_API, ODBC) now dedup by `(source_id, source_path)` — file_hash becomes a change detector rather than identity. Canonical JSON serialization (`sort_keys=True`, UTF-8, newline-separated) is applied at serialization time so field-order rotation no longer causes false "new document" inserts. `POST /datasources/test-connection` performs a double-fetch 500ms apart and warns on hash mismatch with differing key list — envelope pollution surfaces at config time, not three weeks post-GA. `ingest_structured_record` wraps the compare-hash / update path in `SELECT … FOR UPDATE` so two concurrent workers can't race to produce non-deterministic chunk counts. On content UPDATE, old Chunk rows and pgvector embeddings are atomically DELETE-then-re-generate in the same transaction — no stale search results. `documents.connector_type` + `updated_at` columns added; partial UNIQUE indexes `uq_documents_binary_hash` (binary) and `uq_documents_structured_path` (structured). Migration 014 includes dedup DELETE of pre-existing duplicates by `MAX(ingested_at)`. 382+19 tests passing.
- `RestApiConnector`: generic REST connector supporting API key, Bearer, OAuth2 (client credentials), and Basic auth. Configurable pagination (page/offset/cursor/none), response formats (JSON/XML/CSV), max_records cap, 50MB per-fetch size guard, and `since_field` incremental sync.
- `OdbcConnector`: tabular data source connector via pyodbc. Row-as-document (JSON), SQL injection guard on all identifier fields, DSN component error scrubbing, 10MB per-row size guard, incremental sync via `modified_column`.
- `connectors/retry.py`: shared HTTP retry utility — exponential backoff with ±20% jitter, Retry-After header support, 600s ceiling (D-FAIL-12), per-request 30s timeout. Test-connection path bypasses retry for fast admin feedback.
- Migration 013: adds `last_sync_cursor` column and `rest_api`/`odbc` to `source_type` enum.
- `POST /datasources/test-connection` extended for `rest_api` and `odbc` source types (10s timeout, credential scrubbing).
- Frontend wizard: Step 2 now branches on `rest_api` and `odbc` source types with full config forms and credential masking.
- **Deadline notifications (§17 priority 3):** Celery beat now fires `request_deadline_approaching` (requests due within 3 days) and `request_deadline_overdue` (past-deadline requests) notifications daily. Core logic in `backend/app/requests/deadline_check.py`; beat tasks wired in `backend/app/ingestion/scheduler.py`. Recipient is the assigned staff user; requests with no `assigned_to` are skipped. Deduplication prevents re-firing within 23 hours. Templates were already seeded (§8.4). 9 new tests (278→287).
- **Focus visibility (Session A of accessibility audit):** Global `:focus-visible` outline fallback in `frontend/src/globals.css @layer base` targeting `a`, `[role="link"]`, and `[tabindex]:not([tabindex="-1"]):not([data-slot])`. Uses 2px outline in brand `--ring` (#1F5A84) with 2px offset. Excludes `[data-slot]` so it does not double-stack with the Tailwind `focus-visible:ring-3 focus-visible:ring-ring/50` that shadcn Button, Input, and SelectTrigger already ship. Closes spec §13 "Focus visibility" requirement; spec §17 priority #1 sub-item 1a.
- **`request_received` notification dispatch:** `create_request` now calls `queue_notification("request_received", ...)` when `requester_email` is present. Pattern mirrors `update_request`'s PATCH-dynamic dispatch. Closes the last router-side gap in the §8.3 dispatch matrix. Two new regression tests in `test_notification_dispatch.py` (positive + negative), passing fail-before / pass-after sanity check. Test suite 274 → 276.
- **Rule 9 Mandatory Deliverables (`c433beb`, 2026-04-16):** UML architecture diagrams (class, component, sequence, deployment, activity) added to `docs/`. README in `.txt`, `.docx`, and `.pdf` formats with UML embedded. USER-MANUAL scaffolded in `.md`, `.docx`, `.pdf`. `docs/index.html` updated with all four required action buttons (Repo, Download Installer, User Manual, README). GitHub Discussions seeded with starter posts across all enabled categories.
- **USER-MANUAL Complete (`9c1d98b`, 2026-04-16):** Three-section user manual completed in `.md`, `.docx`, and `.pdf` — Section A (End-User, plain-language walkthroughs of every feature), Section B (Technical, full configuration and API reference), Section C (Architectural, UML diagrams with written explanations of every major subsystem).

### Changed
- **Department Names on Users Page:** UUID column replaced with human-readable department names via /departments/ API lookup
- **Legacy .xls Blocklisted:** Removed .xls from XlsxParser supported extensions — BIFF8 binary format cannot be macro-stripped with ZIP approach
- **Dead CSS Selector Removed:** `a.nav-link` in globals.css was unreachable (WCAG 44px applied via Tailwind inline on sidebar NavLinks)
- **Version Alignment:** config.py, pyproject.toml, package.json, and CHANGELOG all at 1.1.0
- **Canonical spec imported at v3.1:** `docs/UNIFIED-SPEC.md` replaced with the v3.1 repo-verified canonical (was v2.0). Source `.docx` preserved at `docs/CivicRecordsAI-UnifiedSpec-v3.1.docx`. Eleven corrections applied during import: §8.3 rewritten with the audited notification dispatch matrix; status count "11 statuses" → "10 statuses" in 4 places; §6.6 `notification_log` and §6.7 `exemption_rules` column lists corrected; §17 priority #5 marked DONE inline; §14 documentation suite row updated; Appendix B footer updated. See commit `1b4795d`.
- **Spec post-Session A hotfix:** §1 test suite line and §2 summary line now read 276 tests. §7.2 typography note rewritten to explain the pre-`2663836` mis-wire and current state. §13 accessibility table focus-visibility row marked Met (post-v1.1.0 in `2663836`) with the full selector and token explanation — **this claim is corrected below by Session B**. §15 release history adds an `_unreleased_` row for post-v1.1.0 work. §16 capability summary test row updated to 276; a11y audit row split into "focus visibility implemented" vs. "keyboard nav / form errors / screen reader audit pending." §17 priorities restructured: accessibility audit broken into sub-items (1a done, 1b–1d pending); deadline notifications promoted to item 3; CHANGELOG font correction marked done.
- **CLAUDE.md context-mode section:** Rewritten from a short "Context Mode (MANDATORY)" note into the full 4-Stage Context-Mode Protocol (GATHER → FOLLOW-UP → PROCESS → WRITE), with forbidden/allowed Bash verb lists, a refusal template, the `context-mode-gate.sh` PreToolUse hook reference, and the `"override hard rule 10"` bypass phrase. Commit `2685f00`. Process/tooling only, no code.
- **Session B accessibility audit — 14-page keyboard navigation walk.** Four pages walked live via Chrome MCP with injected JS reading computed styles after a real Tab keystroke (Login, Dashboard, Requests, RequestDetail); ten pages audited via static source read (Search, Exemptions, DataSources, Ingestion, Users, Onboarding, CityProfile, Discovery, Settings, AuditLog). Findings dropped into spec §13.2 (requirements summary), §13.3 (per-page scoring table), §13.4 (F1–F7 details), and §13.5 (remediation sequencing). Seven findings:
  - **F1 — Tailwind v4 `ring-3` utility silently missing** on every shadcn primitive (Button, Input, SelectTrigger). The v3 alias was removed in Tailwind v4; the CSS bundle contains zero rules matching `.focus-visible\:ring-3:focus-visible`, and computed `--tw-ring-shadow` is `0 0 #0000` on a genuinely keyboard-focused primitive. Only `focus-visible:border-ring` renders, producing a 1px border color swap that likely fails WCAG 2.2 AA 1.4.11 Non-text Contrast.
  - **F2 — `data-table.tsx` row onClick without keyboard handler** — WCAG 2.1.1 hard fail on the Requests page. A keyboard-only staff member cannot open a records request from the list. Blast radius is one page (sole `onRowClick` consumer) but the bug is in the shared component. Most user-visible accessibility bug in the audit.
  - **F3 — base-ui Select hidden form-input leaks into tab order** (every page using `<Select>`; live-confirmed on Requests filter bar which registers 10 tab stops for 6 visible controls).
  - **F4 — SelectTrigger missing `aria-label`** on all Requests filter dropdowns; inferred system-wide.
  - **F5 — data-loading pages lack `aria-live` / `aria-busy` regions** (every page with async data; confirmed live on Dashboard and Requests).
  - **F6 — RequestDetail heading hierarchy is flat** (`<h1>=1, <h2>=0` for a 5-section page).
  - **F7 — non-WCAG observation:** sidebar nav order buries Dashboard 9th.
- **Self-correction to the Session A `Added` entry above.** The "Focus visibility (Session A of accessibility audit)" bullet claimed the shadcn primitives ship a 3px focus ring. That claim is accurate at the **CSS class-presence level** but **not at the render level** — Session B's live walkthrough proved the `ring-3` utility is silently absent from the compiled CSS. The global `:focus-visible` outline fallback added to `globals.css` still renders correctly on bare `<a>`, `[role="link"]`, and non-primitive `[tabindex]` elements (that part of the Session A entry is accurate). **What is wrong is the shadcn primitive half of the claim.** Spec §13 focus-visibility row has been corrected from Met to Partial. Phase 1 hotfix commit `b6627db` made the original misstatement based on class-presence inspection, not computed-style verification — that error is owned and documented here on the permanent record. Remediation is queued as **Session B.1 = F2 + F1** (F2 first because its severity is orders of magnitude higher).

### Fixed
- **Notification Event-Type Mismatch:** Aligned 12 seed templates with router dispatch strings — all 5 dispatch paths now deliver notifications instead of silently no-oping on 3 of 5
- **Notification Seed Production Run:** Confirmed execution against production DB (5 created, 7 skipped)
- **Audit Log CSV Export:** Frontend export button now uses authenticated fetch with ?format=csv and blob download instead of bare anchor tag (was returning 401)
- **Dockerfile:** Added compliance_templates/, scripts/, and tests/ to COPY directives — compliance template test was failing on clean builds
- **city_name in Notifications:** All 5 queue_notification call sites now include city_name from CityProfile — 8 templates were silently failing at render time due to missing template variable
- **GitHub Pages Build:** Added .nojekyll to docs/ — Jekyll was failing on spec markdown files, causing 59 consecutive failed pages-build-deployment runs
- **Geist Variable font actually wired:** `frontend/src/main.tsx` now imports `@fontsource-variable/geist`, so Vite bundles and serves the font (three woff2 variants). Previously it was listed as a dependency but never imported — the rendered font was falling back to the system sans stack. `frontend/src/globals.css` body `font-family` and `frontend/tailwind.config.js` `fontFamily.sans` both updated from "Inter" to "Geist Variable". The v1.0.0 entry below (which had claimed "Inter typography scale") is also corrected to "Geist Variable typography scale" since that was always the intent.
- **Mark Fulfilled button 404 (from the April 13/14 session):** `RequestDetail.tsx` was posting to `POST /requests/{id}/sent`, a route that does not exist. Changed the action from `"sent"` to `"fulfilled"` and extended `handleAction` to route `"fulfilled"` through PATCH alongside `"searching"`. Removed the `sent` display alias from `status-badge.tsx`.
- **Legacy `RequestStatus.SENT` enum value removed:** Migration `010_remove_sent_status.py` performs a defensive UPDATE → drop column default → rename-recreate dance → restore default → drop old enum type. `VALID_TRANSITIONS`, `/stats` active filters, and analytics `closed_statuses` all updated. 11 statuses → 10. Downgrade is intentional no-op (matches migration 008's pattern).
- **Schema drift repaired:** Migration `011_fix_schema_drift.py` adds three columns that existed in SQLAlchemy models but were missing from Alembic migrations — `notification_log.subject` (VARCHAR 500 nullable), `notification_log.body` (TEXT nullable), `exemption_rules.version` (INTEGER NOT NULL DEFAULT 1). Integration tests had been masking the drift by using `create_all()` instead of walking migrations.
- **Session B.1 accessibility fixes — F2 + F1:**
  - **F2 resolved (WCAG 2.1.1):** `data-table.tsx` TableRow now has `tabIndex={0}`, `role="button"`, and `onKeyDown` handling Enter/Space (with `e.preventDefault()`). Keyboard-only staff can now open records requests from the Requests list. Post-fix verification: `focusVisible: true` on focused `<tr role="button">`, Enter and Space both navigated to `/requests/<uuid>`. Sequenced first because this was a functional blocker on the core workflow — highest user-visible severity in the entire audit.
  - **F1 resolved (WCAG 1.4.11):** `ring-3` → `ring-[3px]` on `button.tsx:7`, `input.tsx:12`, `select.tsx:44`. The Tailwind v4 `ring-3` utility was silently missing (v3 alias removed); the arbitrary-value replacement emits correctly. Post-rebuild computed-style verification: `--tw-ring-shadow` = `0 0 0 calc(3px + 0px) hsl(207 62% 32% / .5)`, `box-shadow` = `rgba(31, 87, 132, 0.5) 0px 0px 0px 3px` on keyboard-focused Button (Dashboard), Input (Onboarding "City Name"), and SelectTrigger (Requests filter bar). `focusVisible: true` on all three.
- **Session B.2/C accessibility fixes — F3–F6 (this commit):**
  - **F3 resolved (no code change):** DOM inspection confirmed base-ui v1.3.0 already sets `tabindex="-1"` on its hidden form input. Requests filter bar: 4 tab stops for 4 visible controls (was 10 for 6). No upstream fix or CSS selector needed.
  - **F4 resolved (WCAG 1.3.1):** `aria-label` added to all 15 SelectTriggers across 5 pages — `Exemptions.tsx` (1: "Exemption category"), `Onboarding.tsx` (5: "State", "Population band", "Email platform", "Dedicated IT department", "Monthly records request volume"), `Requests.tsx` (4: "Status filter", "Department filter", "Priority filter", "Assigned to filter"), `Search.tsx` (2: "File type filter", "Department filter"), `Users.tsx` (3: "User role" ×2, "Department"). All 4 Requests filter triggers show non-null `aria-label` attributes in DOM.
  - **F5 resolved (partial):** Created `frontend/src/components/loading-region.tsx` — `<div aria-live="polite" aria-busy={loading}>` wrapper. Applied to DataTable in Requests, AuditLog, Users, Exemptions; to results block in Search. `role="status"` + `aria-label` added to early-return loading `<div>` in Dashboard ("Loading dashboard data") and DataSources ("Loading data sources"). Remaining pages (RequestDetail, Ingestion, CityProfile, Onboarding) carry forward to Session C.
  - **F6 resolved:** Added polymorphic `as?: React.ElementType` prop to `CardTitle` in `frontend/src/components/ui/card.tsx` (defaults to `"div"`; note: `@radix-ui/react-slot` not installed — project uses base-ui). Applied `as="h2"` to 7 sections in `RequestDetail.tsx`: Request Details, Attached Documents, Timeline, Messages, Fees, Response Letter, Workflow. `<h1>=1, <h2>=7` post-edit.
  - **`<tr role="button">` SR proxy:** Row has `role="button"`, `tabIndex=0`. Cell content is in child `<td>` elements with standard table semantics — accessible name computed from cell text by AT row-traversal. Enter and Space key activation verified in Session B.1.
  - **Dialog focus trap:** Verified on Exemptions new-exemption modal. `focusInsideDialog=true` on open; Tab cycles within dialog. Escape is a pre-existing controlled-dialog behavior (`showForm` state managed by `Exemptions.tsx`); not introduced by our changes.
  - **Form error handling (1d) — NOT MET:** Login "Login failed" error is `<p class="text-destructive">` with no `role="alert"`, no `aria-live`, no `aria-describedby`. Visual-only — screen readers will not announce it. Flagged for Session C.
- **Liaison scoping (§17 priority 2):** LIAISON-role users can now access department-scoped Requests and Search. Backend: `require_role` minimum lowered from STAFF to LIAISON on `GET /requests/`, `GET /requests/stats`, `GET /requests/{id}`, and `POST /search/query`; `execute_search` injects `department_id` into search filters automatically for all non-admin users with a department (audit log integrity preserved — `SearchQuery` stores original `req.filters`); Alembic migration 012 adds LIAISON and PUBLIC enum values; search engine dept filter corrected to `d.department_id` on documents table (276→278 tests). Frontend: `App.tsx` fetches `/api/users/me` for role; `SidebarNav` hides Users, Audit Log, and Onboarding items for LIAISON; `LiaisonGuard` redirects direct navigation to hidden routes.
- **Session C accessibility fixes — form error ARIA + F5 completion + Search live region:**
  - **Form error ARIA (1d) resolved (WCAG 4.1.3):** `role="alert"` added to every form-error container across 8 locations in 6 pages — `Login.tsx` (1: page-level error `<div>`), `Users.tsx` (3: create-dialog formError, page-level error, edit-dialog editError), `Exemptions.tsx` (1: page-level error `<Card>`), `DataSources.tsx` (1: page-level error `<Card>`), `Onboarding.tsx` (1: submit error `<p>`), `Requests.tsx` (1: page-level error `<Card>`). `role="alert"` carries implicit `aria-live="assertive"` + `aria-atomic="true"` — screen readers announce the error immediately when it mounts. `setError("")` / `setFormError("")` called before each submit ensures the container unmounts/remounts on each error, guaranteeing re-announcement. Commits: `226453c` (Login), `98791d6` (Users), `47b92a3` (Exemptions, DataSources, Onboarding, Requests).
  - **F5 completed (WCAG 4.1.3):** `role="status"` + `aria-label` added to the early-return loading skeleton `<div>` in `RequestDetail.tsx` ("Loading request details"), `Ingestion.tsx` ("Loading ingestion dashboard"), and `CityProfile.tsx` ("Loading city profile"). Completes F5 across all 7 affected pages (Dashboard and DataSources were done in B.2/C). Commit: `b8d60ae`.
  - **Search `aria-live` restructured:** Replaced the `LoadingRegion` wrapper (which was placed inside the `{results && !loading}` conditional — `aria-busy` was always `false` when mounted) with a persistent `<div aria-live="polite" aria-busy={loading} aria-label="Search results">` gated on `(loading || hasSearched)`. `aria-busy` now correctly transitions `true → false` when results arrive, triggering screen-reader announcement. Removed unused `LoadingRegion` import. TypeScript build: EXIT:0. Commit: `bdfc230`.
- **Retry-After crash fix + grace period activation (`301c4f3`, 2026-04-17):** `RestApiConnector` was crashing on non-integer Retry-After header values (e.g., HTTP-date format); now robustly parsed — integers used directly, HTTP-date strings converted via `email.utils.parsedate_to_datetime`, all values capped at 600s (D-FAIL-12). Grace period bug fixed: circuit breaker was resetting the consecutive-failure threshold from 2 back to 5 immediately after unpause; now holds at 2 until the first successful sync run clears it. Two new integration tests: `test_grace_period_trips_circuit_at_2_failures_not_5` and `test_grace_period_clears_on_success`.
- **Landing page User Manual link (`23f0655`, 2026-04-16):** "User Manual" action button in `docs/index.html` was pointing to a non-existent GitHub Pages path. Corrected to the deployed PDF URL.

### Security
- **ReDoS Protection:** Exemption rule test endpoint uses `regex` library with timeout=2s for admin-entered patterns — prevents catastrophic backtracking
- **Test-Connection Credential Safety:** POST /datasources/test-connection uses dedicated schema, never persists credentials, never logs connection strings, never returns credentials in response
- **Self-Demotion Guard:** Admins cannot change their own role or deactivate their own account via the PATCH endpoint
- **Macro Stripping:** VBA macros stripped from DOCX/XLSX before ingestion — defense-in-depth for document pipeline security

### Tests
- 430 total tests (425 backend + 5 frontend) — up from 80 in v0.1.0, 104 at v1.0.0, 274 at v1.1.0-pre-P7
- +28 backend tests in P7 (sync failures, circuit breaker, retry logic, health status, unpause, Sync Now)
- +2 grace period integration tests: `test_grace_period_trips_circuit_at_2_failures_not_5` and `test_grace_period_clears_on_success`
- +13 backend tests in P6b (cron scheduler, schedule validation, adversarial pattern rejection)
- +19 backend tests in P6a (idempotency contract, hash collision, race condition)
- +9 backend tests for deadline notifications (due-in-3-days, overdue, deduplication)
- 5 frontend tests: `useSyncNow` polling lifecycle (stays disabled until completion, shows elapsed time)
- Template render mismatch test catches any notification template referencing variables not provided by the router
- Seed coverage test ensures every router-dispatched event_type has a matching template
- `.xls` blocklist test prevents accidental re-addition of legacy format

## [1.0.0] - 2026-04-12

### Added
- **Design System:** shadcn/ui component library with civic design tokens (#1F5A84 primary), Geist Variable typography scale, sidebar layout shell
- **Sidebar Navigation:** Grouped navigation (Workflow / Setup / Administration) replacing top nav bar, 44px touch targets, active page indicator
- **11 Pages:** Dashboard, Search, Requests, Request Detail, Exemptions, Sources, Ingestion, Users, Onboarding Interview, City Profile, Discovery Dashboard
- **Onboarding Interview:** 3-phase wizard (City Profile, System Identification, Gap Map) for first-time city deployment
- **City Profile API:** GET/POST/PATCH /city-profile for persistent city configuration with gap map
- **Municipal Systems Catalog:** 12 functional domains, 25+ vendor systems in bundled JSON with auto-loader on startup
- **Request Timeline:** Event history on every request with automatic logging on status transitions
- **Request Messages:** Internal/external messaging thread on each request
- **Fee Tracking:** Fee line items per request with automatic total calculation
- **Response Letter Generation:** LLM-assisted draft letters with template fallback, labeled as AI-generated draft
- **Notification Service:** Template-based notification system with queue_notification() helper, template CRUD API
- **Operational Analytics:** GET /analytics/operational with response time, deadline compliance, overdue count, status breakdown
- **Connector Framework:** Universal connector protocol (authenticate/discover/fetch/health_check) with file system implementation
- **Tier 1 PII Expansion:** Credit card (Luhn-validated), bank routing/account numbers, state-specific driver's license patterns (CO, CA, TX, NY, FL)
- **Context Manager:** Token budgeting for local LLM calls with priority-based context assembly
- **11 Request Statuses:** received, clarification_needed, assigned, searching, in_review, ready_for_release, drafted, approved, fulfilled, closed
- **StatusBadge Component:** Color+icon mapping for all statuses across request, document, and exemption domains (colorblind accessible)
- **StatCard, PageHeader, EmptyState, DataTable:** Reusable design system components with loading, empty, and error states
- **Skip-to-content Link:** Screen reader accessibility (WCAG 2.4.1)
- **Discovery Dashboard Shell:** v1.1 preview page with feature explanation

### Changed
- **UI Redesign:** All pages migrated from raw Tailwind to shadcn/ui design system with civic color tokens
- **Ingestion Filenames:** UUID prefixes stripped from display — original filenames shown
- **Timestamps:** Relative display ("3 hours ago") alongside absolute dates
- **Search Scores:** RRF scores normalized to 0-100% with visual progress bar
- **Empty States:** Smart contextual guidance instead of blank screens ("No flags reviewed yet" instead of "0.0%")
- **Request Forms:** Collapsible inline forms replaced with Dialog modals
- **Status Badges:** Color-only badges replaced with icon+color badges for accessibility
- **Navigation:** Top nav bar replaced with sidebar layout (240px fixed, 56px header)

### Fixed
- **Dockerfile.backend:** Added missing `data/` directory copy for systems catalog
- **Catalog Loader:** Graceful handling when systems_catalog.json not found (no crash on startup)
- **Sidebar Footer:** Shows user email instead of UUID (via /users/me endpoint)

### Security
- All new endpoints require role-based authentication
- All mutations audit-logged
- Notification credentials never logged or displayed after entry
- Response letters labeled as "AI-GENERATED DRAFT — REQUIRES HUMAN REVIEW"
- CJIS compliance gate designed for public safety connectors (Section 12)

## [0.1.0] - 2026-04-12

### Added
- **Foundation:** Docker Compose stack with PostgreSQL+pgvector, Redis 7.2, Ollama, FastAPI, Celery, React frontend
- **Authentication:** JWT-based auth with 4 roles (Admin, Staff, Reviewer, Read-Only) via fastapi-users
- **Service Accounts:** API key generation for federation between CivicRecords AI instances
- **Audit Logging:** Hash-chained, append-only audit log with CSV/JSON export and chain verification
- **Document Ingestion:** Two-track pipeline — 7 file type parsers (PDF, DOCX, XLSX, CSV, email, HTML, text) + Gemma 4 multimodal OCR with Tesseract fallback
- **Chunking:** Sentence-aware text chunking with configurable overlap
- **Embeddings:** nomic-embed-text via Ollama with batch support, stored in pgvector
- **Hybrid Search:** pgvector semantic similarity + PostgreSQL full-text search combined via Reciprocal Rank Fusion
- **LLM Synthesis:** Optional AI-generated answer summaries from search results (labeled as AI draft)
- **Search Sessions:** Query history tracking with iterative refinement
- **Request Tracking:** Records request lifecycle management with status workflow (received → searching → in_review → drafted → approved → sent)
- **Document Attachment:** Link search results to requests with automatic document caching for legal defensibility
- **Deadline Management:** Approaching deadline and overdue alerts on request dashboard
- **Exemption Detection:** Rules-primary engine with built-in PII patterns (SSN, phone, email, credit card, DOB) + per-state keyword rules
- **LLM Exemption Suggestions:** Optional secondary exemption detection via Ollama, confidence capped at 0.7
- **Colorado CORA Pilot:** Pre-configured exemption rules for Colorado Open Records Act categories
- **Exemption Review Workflow:** Accept/reject flags with audit trail and acceptance rate dashboard
- **Disclosure Templates:** Configurable compliance document templates (AI disclosure, response letters)
- **Model Transparency:** Admin panel showing Ollama model info (name, size, details)
- **Data Sovereignty:** Verification script confirming no outbound data transmission
- **Cross-Platform:** Windows (Docker Desktop), macOS, and Linux support with platform-specific install scripts
- **React Admin Panel:** 8 pages — Login, Dashboard, Search, Requests, Request Detail, Exemptions, Data Sources, Ingestion, Users
- **80 automated tests** covering auth, audit, search, requests, exemptions, parsers, chunking, embeddings

### Security
- All audit logs hash-chained with SHA-256 for tamper evidence
- Human-in-the-loop enforced at API layer (no auto-redaction, no auto-approval)
- All LLM outputs labeled as AI-generated drafts
- No telemetry, analytics, or outbound data transmission
- JWT secrets from environment configuration (not hardcoded)
- API keys hashed before storage (SHA-256)
