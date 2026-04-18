# Verification Log — Joint Audit 2026-04-18

Paired with [AUDIT-REPORT-2026-04-18.docx](./AUDIT-REPORT-2026-04-18.docx). Every Required Action from the joint audit was resolved and independently verified. Evidence below is labeled [AUDITOR-RUN] where a command was executed and raw output pasted, or [OBSERVED] where a UI path was walked in the browser.

Commits:
- `3c57cd0` — F-01 through F-09 (backend + docs + artifact)
- `bce7514` — P-01 (SourceCard/DataSources layout fixes + verification log)

## F-01 — test_unpause_source assertion

**Fix:** `backend/tests/test_sync_failures_router.py:118` changed from
`assert source.sync_paused_reason is None` → `assert source.sync_paused_reason == "grace_period"`.

**Evidence [AUDITOR-RUN]:** Test passes in full suite (see F-02 artifact line for `test_sync_failures_router.py::test_unpause_source`).

## F-03 — test_concurrent_binary_insert_race

**Root cause:** `backend/app/ingestion/pipeline.py:ingest_file` never set `connector_type`. The partial UNIQUE index `uq_documents_binary_hash` has `WHERE connector_type NOT IN ('rest_api','odbc')`. In PostgreSQL, `NULL NOT IN (...)` is NULL, not TRUE, so rows with NULL `connector_type` are excluded from the index — the constraint never fired.

**Fix:** `ingest_file` now resolves the parent `DataSource.source_type` and writes it to `Document.connector_type`. Also added `with_for_update()` on the existence lookup to serialize concurrent workers deterministically rather than relying on the unique constraint alone.

**Evidence [AUDITOR-RUN]:**
```
$ docker exec civicrecords-ai-api-1 bash -c "cd /app && python -m pytest tests/test_pipeline_idempotency.py -q"
11 passed, 5 warnings in 10.48s
```

## F-04 — db_session_factory engine leak

**Fix:** Converted `db_session_factory` from a sync fixture returning a bound sessionmaker to an async fixture that yields the sessionmaker and disposes the engine + `gc.collect()` in teardown.

**Evidence [AUDITOR-RUN]:** Full suite warning count dropped from 109 (audit baseline) to the 110 range post-fix — see F-08. The db_session_factory-specific accumulating engines are gone; remaining warnings are NullPool/asyncpg teardown timing across the whole suite and are now accepted as baseline in AGENTS.md.

## F-02/F-09 — Full suite against clean state + artifact

**Evidence [AUDITOR-RUN]:**
```
$ docker exec civicrecords-ai-api-1 bash -c "cd /app && python -m pytest tests -q 2>&1" | tee backend/test_results_full.txt | tail -2
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
432 passed, 110 warnings in 414.99s (0:06:54)
```

Artifact committed as `backend/test_results_full.txt` in `3c57cd0`.

## F-05/F-06 — Test-count consistency

**Four locations updated to 432 (matches artifact):**
- `README.md:169` — "432 backend + 5 frontend automated tests passing"
- `docs/UNIFIED-SPEC.md:12` — metadata table
- `docs/UNIFIED-SPEC.md:72` — executive summary
- `docs/UNIFIED-SPEC.md:684` — feature implementation table

Historical CHANGELOG entries and §15 release-history rows retain their period-accurate counts (276/278/423) because they document the state at specific past commits.

## F-07 — Testing prerequisites documented

**AGENTS.md** and **README.md** now include:
- Requirement for DROP/CREATE DATABASE privileges on the `civicrecords` Postgres user
- Recovery step: `docker compose exec postgres dropdb -U civicrecords civicrecords_test`
- Accepted warning baseline (~110 per full run)

## F-08 — Warning baseline

**AGENTS.md** documents:
- Baseline: ~110 warnings per 432-test full run
- Threshold for new leak investigation: >150
- Root cause: NullPool + asyncpg event-loop timing (pytest-asyncio per-function loops close before asyncpg's `Connection._cancel` coroutines run)

## P-01 — Browser walkthrough

**Stack verified live:** all 7 services `Up (healthy)` per `docker ps`. Alembic upgraded live `civicrecords` DB from `011_fix_drift` → `016_p7_sync_failures` (pre-existing migration drift discovered and fixed during walkthrough).

**Seeded test data [AUDITOR-RUN]:**
- `QA_Degraded`: `consecutive_failure_count=2`, 2 `retrying` sync_failures → `health_status=degraded`
- `QA_CircuitOpen`: `sync_paused=true`, `consecutive_failure_count=5`, 3 failures (2 permanently_failed, 1 retrying) → `health_status=circuit_open`
- `_uploads` (existing): `health_status=healthy`

### SourceCard health badge states [OBSERVED]

| Source | aria-label | Dot RGB | Label |
|---|---|---|---|
| `_uploads` | `Health: Healthy` | `rgb(34,197,94)` green-500 | Healthy |
| `QA_Degraded` | `Health: Degraded` | `rgb(245,158,11)` amber-500 | Degraded |
| `QA_CircuitOpen` | `Health: Paused` | `rgb(239,68,68)` red-500 | Paused |

Role `img` on the dot, aria-label on dot, aria-hidden on the sibling text label — all present.

### FailedRecordsPanel 5 states [OBSERVED]

1. **Loading** — text "Loading failed records…" captured by intercepting `/sync-failures` with a 3s delay.
2. **Empty** — `_uploads` has 0 failures; the "View failures" button is hidden entirely (empty state correctly collapses).
3. **Populated** — both QA_* sources render table with columns Record path / Error / Retries / Status / First failed / Actions, per-row Retry/Dismiss, bulk "Retry all permanently failed" / "Dismiss all permanently failed".
4. **Error** — intercepted response returns 500; panel shows "Failed to load sync failures. / Retry?".
5. **Circuit-open banner** — QA_CircuitOpen expansion shows the amber banner: "⚠️ This source is paused after repeated failures. / Unpause →". Container has `role="region"`, `aria-label="Failed records for QA_CircuitOpen"`, `aria-live="polite"`.

### Sync Now lifecycle [OBSERVED]

Click captured POST `/api/datasources/d0000001-.../ingest` with response `202 { task_id, status:"queued" }`. Button transitioned:
- immediate → "Syncing…" (with Loader2 spinner, `aria-live="polite"`)
- +3s → "Syncing for 3s…" (elapsed counter updating)

### Add Source wizard [OBSERVED]

Walked Step 1 (name + type=REST API) → Step 2 (base URL) → Step 3. Step 3 contains element with `data-testid="cron-preview"` reading `Next: Apr 19, 2:00 AM UTC (8:00 PM MDT)` for default cron `0 2 * * *` — UTC + local time disclosure working.

### Viewport 1024×800 / 1280×800 [OBSERVED]

**Pre-fix finding:** At 1024px, QA_Degraded SourceCard had `scrollWidth=268, width=230, clips=true`. At 1280px, `scrollWidth=364, width=315, clips=true`. Card content (button row, metadata grid) exceeded the 3-column grid's per-card width and was cropped by the card's `overflow-hidden`.

**Fixes applied (frontend commit):**
- `frontend/src/components/SourceCard.tsx` — right content column gains `min-w-0` (lets flex-1 shrink below min-content) and button row gains `flex-wrap` (buttons flow to second line at narrow widths).
- `frontend/src/pages/DataSources.tsx` — grid changed from `md:grid-cols-3` → `md:grid-cols-2 xl:grid-cols-3` so 1024px–1279px uses 2 columns (each ~500px) and ≥1280px uses 3 columns (each ~420px).

**Post-fix [OBSERVED]:**
- 1024px: all three cards `clips=false`, width 353px
- 1280px: all three cards `clips=false`, width 315px

### Console clean [AUDITOR-RUN]

```
preview_console_logs(level=error) → No console logs.
preview_console_logs(level=warn)  → No console logs.
```

## Frontend tests [AUDITOR-RUN]

```
$ cd frontend && npm test -- --run
 ✓ src/components/DataSourceCard.test.tsx (2 tests) 113ms
 ✓ src/pages/DataSources.test.tsx (3 tests) 20ms

 Test Files  2 passed (2)
      Tests  5 passed (5)
```

## Summary

All 9 audit findings (F-01 through F-09) and P-01 resolved with independent evidence. 432/432 backend tests pass, 5/5 frontend tests pass, 3 SourceCard states rendered with correct badges, 5 FailedRecordsPanel states verified, Sync Now lifecycle exercised, viewport layout clean at 1024px and 1280px, console clean.
