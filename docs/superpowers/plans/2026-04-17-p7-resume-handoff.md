# P7 Progress Report (resume here)

## State
HEAD: `48445d4` (on origin/master)
Tasks 1–3 complete.
Migrations **016** and **017** both applied to test DB.

Note: 017 is a fix-up migration. During Task 3 the implementer removed `ForeignKey("users.id")` from `SyncFailure.dismissed_by` because the test used a random UUID for a non-existent user. That was the wrong direction — the test was wrong, not the schema (dismissal is a compliance artifact, FK enforces integrity). 017 restores the FK; the test was updated to `SELECT id FROM users LIMIT 1` matching sibling-test pattern.

## Remaining tasks
4. `sync_runner.py` with retry layers + circuit breaker + `tasks.py` rewire
5. Notifications stub + sync-failures API endpoints (7 endpoints)
6. `health_status` computation in DataSource list
7. Frontend SourceCard + FailedRecordsPanel + `useSyncNow`
8. 429/Retry-After (D-FAIL-12) + pipeline failure classification (D-FAIL-10)
9. P6 carry-forward cleanup (aiofiles, formatNextRun, shadcn Checkbox, conftest `alembic upgrade head`)
10. Full test suite + docs update (UNIFIED-SPEC §17 5c with captured code SHA, CHANGELOG [Unreleased]/Added, README feature section check, grep consistency)

## Carry-forwards into Task 4 (mandatory)

Four tests in Task 1's `TestCircuitBreakerLogic` mutate MagicMock attributes and assert them back. They pass regardless of `sync_runner` behavior. Task 4 must add real integration tests that call `run_connector_sync_with_retry()` end-to-end and assert DB state, and must audit/update the §17.x Proof Test reference for **D-FAIL-4** to point at one of those real tests.

**Verbatim prompt language to paste into Task 4 subagent dispatch:**

> When you write tests for `test_sync_runner_retry_layers.py` and `test_circuit_breaker.py`, the tests must call `run_connector_sync_with_retry()` end-to-end with a real (or realistic) `sync_failures` table and `DataSource` row, and assert observable state changes in the DB — `consecutive_failure_count` values, `sync_paused` transitions, `sync_failures.status` values — not mutated mock attributes. Before you finish Task 4, open `docs/UNIFIED-SPEC.md` §17.x and verify that the "Proof Test" for D-FAIL-4 points at a test that exercises `sync_runner` code paths. If it points at a tautological mock-mutation test from Task 1, update it to reference one of your new tests. Remove the tautological tests or refactor them. They should not survive Task 4.

Task 4 also contains Steps 9–11 (rewire `ingestion/tasks.py` to call `run_connector_sync_with_retry`, re-run tests, combined commit) — atomicity note already in the plan: migration 016 lands in Task 3 before the continue-on-error flip.

## Plan reference
`docs/superpowers/plans/2026-04-16-p7-sync-failures.md` (committed at `52feea6`)

§17 convention reminder: Task 10 Step 4 hardcodes the P7 final **code** commit SHA into the §17 5c line. Procedure: finish Task 9, run `git rev-parse HEAD`, capture that SHA, start Task 10, hardcode it. No self-referencing SHA. No `--amend`. No force-push. No placeholder.

## Auditor thread
This is a multi-session P7 execution. Same auditor role continues — audit each task after implementer + reviewers, with specific attention to:
- Test body quality (not just presence) — read bodies of tests referenced in §17.x Proof Test column and verify they exercise real code paths, not mock mutation
- Plan deviations raised before commit, not silently patched
- §17.x Proof Test column accuracy

Include the "audit each task" line explicitly because otherwise the next session might default to "just run through it" without the audit loop, and we lose the discipline built across P6a/P6b/P7 tasks 1–3.
