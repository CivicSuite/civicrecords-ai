# CivicRecords AI — Session Handoff

**Date:** 2026-04-16
**Branch:** master
**HEAD:** `2bb5a73` (docs: fix stale §2.5 cross-ref in connector expansion spec v1)
**Status:** Ready to implement Priority 5 — Connector Expansion

---

## What We're Building

Two new data source connectors:
- **`RestApiConnector`** — generic REST API (API key, Bearer, OAuth2, Basic auth)
- **`OdbcConnector`** — on-prem SQL databases via pyodbc

---

## Approved Spec

`docs/superpowers/specs/2026-04-16-connector-expansion-design-v4.md`

This is the canonical spec. Do not use v1/v2/v3. Key decisions locked in:
- `_ensure_authenticated()` guard on every protocol method
- Shared `retry.py` utility (429 backoff); test-connection **bypasses** retry entirely
- `last_sync_cursor` advances only on full successful sync (enforced in sync runner, not connector)
- SQL injection guard: all ODBC identifiers validated with `^[A-Za-z_][A-Za-z0-9_]*$` at model instantiation AND query construction
- OAuth2 reactive 401 refresh scoped to `auth_method == "oauth2"` only
- `close()` no-op on BaseConnector; ODBC overrides; sync runner calls in `finally` block
- Credential fields (`api_key`, `token`, `client_secret`, `password`, `connection_string`) **omitted entirely** from GET API responses — not masked, not null
- `test_connection_safety` test: recursive JSONB walk at all depths (flat `.get()` prohibited)

---

## Implementation Plan

`docs/superpowers/plans/2026-04-16-connector-expansion.md`

12 tasks, full TDD. All code is in the plan — no placeholders.

---

## Execution Mode

Use **`superpowers:subagent-driven-development`**. The plan has 12 tasks and ~15 files. Subagent-driven is required to prevent context drift across tasks.

**Critical process rule from past failures:** After each subagent completes a task, verify the actual files exist on disk and match what the plan specifies before dispatching the next subagent. Do not trust subagent self-reports — check the files.

---

## File Map (what gets created/modified)

| File | Action |
|---|---|
| `backend/app/connectors/base.py` | Modify — add no-op `close()` |
| `backend/alembic/versions/013_add_connector_types.py` | Create |
| `backend/app/models/document.py` | Modify — add REST_API/ODBC to SourceType; add last_sync_cursor |
| `backend/app/schemas/connectors/__init__.py` | Create |
| `backend/app/schemas/connectors/rest_api.py` | Create |
| `backend/app/schemas/connectors/odbc.py` | Create |
| `backend/app/connectors/retry.py` | Create |
| `backend/app/connectors/rest_api.py` | Create |
| `backend/app/connectors/odbc.py` | Create |
| `backend/app/connectors/__init__.py` | Modify — connector factory |
| `backend/app/datasources/router.py` | Modify — test-connection endpoint |
| `backend/app/ingestion/tasks.py` | Modify — cursor semantics + close() |
| `frontend/src/pages/DataSources.tsx` (or wizard file) | Modify — Step 2 branching + masking |
| `docs/UNIFIED-SPEC.md` | Modify — §11.4 status |
| `CHANGELOG.md` | Modify |
| `backend/tests/test_base_connector.py` | Create |
| `backend/tests/test_connector_schemas.py` | Create |
| `backend/tests/test_retry.py` | Create |
| `backend/tests/test_rest_connector.py` | Create |
| `backend/tests/test_odbc_connector.py` | Create |
| `backend/tests/test_ingestion_tasks.py` | Modify |

---

## Key Existing Patterns to Follow

- **`fetch()` signature:** `fetch(self, source_path: str)` — not `fetch(self, record: DiscoveredRecord)` (see `file_system.py`)
- **Migration pattern:** `op.execute("ALTER TYPE ... ADD VALUE IF NOT EXISTS '...'")` — see `008_extend_request_status_enum.py`; downgrade for enum is a documented no-op
- **`DataSource.last_sync_at` already exists** in `models/document.py` line 46 — migration only adds `last_sync_cursor`
- **`SourceType` enum** currently has only `UPLOAD` and `DIRECTORY` — migration adds `REST_API` and `ODBC`
- **`backend/app/connectors/__init__.py`** is currently empty — Task 7 adds factory
- **Celery tasks** use `asyncio.new_event_loop()` pattern via `_run_async` helper — see `ingestion/tasks.py`

---

## Git State

- Local branch is ahead of `origin/master` by 10 commits (all docs/specs/plan)
- No uncommitted changes (except untracked scratch files — do not commit)
- Untracked files to ignore: `CONTEXT-PROMPT.md`, `SESSION-CONTEXT-PROMPT.md`, `build_out.txt`, `test_out.txt`, `docs/AUDIT-REPORT-2026-04-12.md`

---

## Hard Rules Active

- **Rule 9:** All 5 deliverables required before `git push` (README.{txt,docx,pdf}, USER-MANUAL.{md,docx,pdf}, docs/index.html, UML diagram, DISCUSSIONS_SEEDED) — push is blocked
- **Rule 10:** Context-mode hard gate — no Bash for large-output commands
- **Rule 11:** Plan gate — `.claude/plans/*.md` must exist before commit (already satisfied by `docs/superpowers/plans/2026-04-16-connector-expansion.md` — check if gate looks there or in `.claude/plans/`)
- **Rule 12:** Longhand stack integrity gate

---

## Starting Instruction for New Session

> Open `docs/superpowers/plans/2026-04-16-connector-expansion.md`, then invoke `superpowers:subagent-driven-development` to execute it task by task. Verify each task's files exist on disk after each subagent completes before dispatching the next.
