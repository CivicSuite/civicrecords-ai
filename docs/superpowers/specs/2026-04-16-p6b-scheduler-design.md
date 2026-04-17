# P6b — Cron Scheduler Rewrite + Schedule UI States

**Date:** 2026-04-16  
**Status:** Approved for implementation  
**Depends on:** P6a (ships after)  
**Replaces:** `schedule_minutes` interval-based drift scheduler

---

## Problem Statement

The current scheduler (`check_scheduled_sources`) checks `(now - last_ingestion_at) > timedelta(minutes=schedule_minutes)` every 5 minutes. This is interval-based and drifts — a 24-hour sync doesn't run "nightly at 2am," it runs "24 hours after whenever the last run finished." Municipal admins think in clock time. Rate-limited APIs and compliance audit trails ("when did we last pull from X?") require predictable, clock-anchored scheduling. The `sync_schedule` cron field exists in the model but has never been read.

---

## Decision Log

### D1: Switch to cron-based scheduling via `croniter`
**Decision:** `sync_schedule` (String(50), cron expression) is the single scheduling field. `schedule_minutes` is dropped.  
**Why:** `croniter` (Apache 2.0 licensed) parses standard cron expressions and computes next/previous run times in UTC. Cron expressions match how admins think: "nightly at 2am" = `0 2 * * *`. No drift.  
**Scheduler behavior (B1 — corrected):** `check_scheduled_sources` (fires every 5 min) evaluates each active, non-paused source with a non-null `sync_schedule`. For each: compute the next scheduled slot after `last_sync_at` using `croniter(expr, anchor).get_next(datetime)`. If that next slot is ≤ `datetime.now(UTC)`, the source is overdue → trigger.

Correct logic:
```python
anchor = source.last_sync_at or datetime(1970, 1, 1, tzinfo=UTC)
it = croniter(source.sync_schedule, anchor)
next_scheduled = it.get_next(datetime)
if next_scheduled <= datetime.now(UTC):
    task_ingest_source.delay(str(source.id))
```

**Why not `get_prev() > anchor`:** `croniter(expr, anchor).get_prev()` returns the most recent scheduled slot at or before `anchor`. By construction this is almost never `> anchor` (only exactly equal if `anchor` is itself a scheduled moment). For `last_sync_at = yesterday 2:05am` and cron `0 2 * * *`, `get_prev()` returns `yesterday 2:00am` which is NOT `> yesterday 2:05am` — source never triggers even though today's 2am has passed. This was the original spec bug.

**`hash_use_datetime` note:** this parameter does not exist in the standard `croniter` API. Removed.

### D2: Minimum interval validation — rolling week sampling
**Decision:** Reject any cron expression where the minimum interval across a rolling 7-day window is < 5 minutes.  
**Why:** `*/1 0 * * *` looks like "once per minute in hour 0 only" but fires 60 times between midnight and 1am. Checking only `get_next()` from now misses this. Sample the full week.  
**Implementation:**
```python
def min_interval_minutes(expr: str) -> int:
    it = croniter(expr, datetime.now(UTC))
    prev = it.get_next(datetime)
    min_gap = float("inf")
    for _ in range(2016):  # 7 days × 288 ticks/day at 5-min granularity
        nxt = it.get_next(datetime)
        gap = (nxt - prev).total_seconds() / 60
        min_gap = min(min_gap, gap)
        prev = nxt
    return int(min_gap)
```
Validation: `min_interval_minutes(expr) < 5` → reject with message "Schedule fires more frequently than every 5 minutes. Minimum allowed interval is 5 minutes."  
Validated server-side at `DataSourceCreate`, `DataSourceUpdate`, and `test-connection`.

### D3: `schedule_enabled` boolean — preserve expression across toggle
**Decision:** New boolean field `schedule_enabled` (default `True`) on DataSource.  
When `schedule_enabled = False`: scheduler ignores `sync_schedule` even if set. Source is "Manual only."  
**Why:** Don't null `sync_schedule` on disable — admin loses their configured expression and must re-enter it on re-enable. `schedule_enabled = False` preserves the field; re-enabling pre-fills the UI.  
**UI toggle:** "Enable automatic sync" checkbox. When unchecked, schedule picker is hidden but field is preserved in form state. Saved as `schedule_enabled = False`.

### D4: `schedule_minutes` migration (M3 + M4 — non-divisors and silent loss)
**Decision:** Migration converts `schedule_minutes` to cron using an explicit allowlist. Values not on the allowlist are nulled with a migration report — no silent data loss.

**Allowlist (clean cron-representable intervals):**

| schedule_minutes | cron | Notes |
|---|---|---|
| 5 | `*/5 * * * *` | minimum allowed |
| 10 | `*/10 * * * *` | |
| 15 | `*/15 * * * *` | |
| 20 | `*/20 * * * *` | |
| 30 | `*/30 * * * *` | |
| 60 | `0 * * * *` | anchored to :00 |
| 120 | `0 */2 * * *` | anchored to even hours |
| 180 | `0 */3 * * *` | |
| 240 | `0 */4 * * *` | |
| 360 | `0 */6 * * *` | |
| 480 | `0 */8 * * *` | |
| 720 | `0 */12 * * *` | |
| 1440 | `0 2 * * *` | daily, anchored to 2am UTC |

**Non-allowlist values (e.g., 45, 3, 90, 100):** Set `sync_schedule = NULL`, `schedule_enabled = False`. Do NOT silently convert — `*/45 * * * *` is NOT a 45-minute interval (fires at :00 and :45, leaving a 15-minute gap at top of hour). Emit a migration report entry for every nulled source:
```
MIGRATION REPORT: schedule_minutes → sync_schedule conversion
  Source ID {uuid} (name: "{name}"): schedule_minutes={N} has no clean cron equivalent.
  sync_schedule set to NULL, schedule_enabled set to False.
  Admin action required: set a schedule manually in the DataSources UI.
```
Report is written to migration log (Alembic output) and also to a `_migration_015_report` table for admin visibility.

As of 2026-04-16, no production rows have `schedule_minutes` set (UI never exposed it). State this in the migration comment so reviewers can verify.

### D4b: Timezone — UTC at storage, local conversion in UI (H6)
**Decision:** All cron expressions are stored and evaluated in UTC. The scheduler uses `datetime.now(UTC)` exclusively.  
**Why UTC:** single-tenant per-city deploy means the server timezone is not reliably the admin's timezone. UTC is unambiguous, avoids DST gaps, and is what croniter expects.  
**UI disclosure (required):** anywhere a cron expression or computed next-run time is shown, display both UTC and local time:  
- Card: "Next: Apr 17 at 2:00 AM UTC (8:00 PM MDT)"
- Wizard schedule picker: "All schedules run in UTC. `Nightly at 2am` = 2:00 AM UTC."
- Custom cron input: tooltip "Your cron expression is evaluated in UTC."  
**Why this matters:** an admin typing `0 2 * * *` intending "2 AM local" gets 2 AM UTC, which is 9 PM or 7 PM local depending on timezone. For a compliance product, a sync that runs at 7 PM instead of 2 AM is not just surprising — it's an audit trail discrepancy.  
**Local time computation:** browser-side, using `Intl.DateTimeFormat` to detect and display local offset. No server-side timezone handling needed.  
**Test:** `test_scheduler.py::test_cron_evaluated_in_utc` — create source with `0 2 * * *`, mock `datetime.now` to a UTC time that is 2 AM UTC, verify trigger. Mock to 2 AM local (non-UTC) time, verify NO trigger if UTC time is different.

### D5: Three-state card schedule display
| DataSource state | Display |
|---|---|
| `sync_schedule IS NULL OR schedule_enabled = False` | **"Manual only"** (gray text, no clock icon) |
| `schedule_enabled = True` AND `sync_paused = False` | **"Next: Apr 17 at 2:00 AM"** (computed via `croniter.get_next()` from `last_sync_at`) |
| `sync_paused = True` | **"Paused — check failed records"** (amber, links to failed records panel) |

### D6: Schedule presets UI
Preset dropdown maps human labels to cron strings:

| Label | Cron |
|---|---|
| Every 15 minutes | `*/15 * * * *` |
| Every 30 minutes | `*/30 * * * *` |
| Every hour | `0 * * * *` |
| Every 6 hours | `0 */6 * * *` |
| Every 12 hours | `0 */12 * * *` |
| Nightly at 2am | `0 2 * * *` |
| Weekly (Mon 2am) | `0 2 * * 1` |
| Custom… | (reveals cron text input) |

Custom input: shows raw cron expression, inline validation on blur, min-interval error shown inline.

---

## Schema Changes

**Migration 015_p6b_scheduler.py:**

```sql
-- 1. Add schedule_enabled
ALTER TABLE data_sources ADD COLUMN schedule_enabled BOOLEAN NOT NULL DEFAULT TRUE;

-- 2. Migrate schedule_minutes → sync_schedule (see D4 logic)
UPDATE data_sources SET sync_schedule = ... WHERE schedule_minutes IS NOT NULL;

-- 3. Drop schedule_minutes
ALTER TABLE data_sources DROP COLUMN schedule_minutes;

-- 4. Add croniter-validated check constraint (basic sanity, not full validation)
-- Full validation is in Python; DB constraint prevents empty strings
ALTER TABLE data_sources ADD CONSTRAINT chk_sync_schedule_nonempty
  CHECK (sync_schedule IS NULL OR length(trim(sync_schedule)) > 0);
```

**DataSourceCreate / DataSourceUpdate:** add `sync_schedule: str | None`, `schedule_enabled: bool = True`. Remove `schedule_minutes`.  
**DataSourceRead:** add `sync_schedule`, `schedule_enabled`, remove `schedule_minutes`. Add `next_sync_at: datetime | None` (computed field, not stored — returned by API via `croniter.get_next()` at response time).

---

## Scheduler Changes (`backend/app/ingestion/scheduler.py`)

`check_scheduled_sources` rewrite:
```python
async def check_scheduled_sources():
    result = await session.execute(
        select(DataSource).where(
            DataSource.is_active == True,
            DataSource.schedule_enabled == True,
            DataSource.sync_paused == False,
            DataSource.sync_schedule.isnot(None),
        )
    )
    sources = result.scalars().all()
    now = datetime.now(UTC)
    triggered = 0
    for source in sources:
        anchor = source.last_sync_at or datetime(1970, 1, 1, tzinfo=UTC)
        it = croniter(source.sync_schedule, anchor)
        next_scheduled = it.get_next(datetime)
        if next_scheduled <= now:
            task_ingest_source.delay(str(source.id))
            triggered += 1
    return {"checked": len(sources), "triggered": triggered}
```

---

## Test Plan

| Test | File::Function | Description |
|---|---|---|
| Cron trigger — overdue | `test_scheduler.py::test_overdue_source_triggers` | Source with `0 2 * * *`, `last_sync_at` = yesterday → triggered |
| Cron trigger — not due | `test_scheduler.py::test_not_due_source_skipped` | Source with `0 2 * * *`, `last_sync_at` = today at 2:01am UTC → not triggered |
| Cron trigger — first run | `test_scheduler.py::test_null_last_sync_triggers_immediately` | Source with `last_sync_at = NULL` → triggered immediately |
| UTC evaluation | `test_scheduler.py::test_cron_evaluated_in_utc` | `0 2 * * *`, now=2:01 UTC → trigger; now=2:01 local non-UTC → no trigger |
| Min interval — fine | `test_scheduler.py::test_min_interval_valid_hourly` | `0 * * * *` (hourly, 60-min gap) → passes validation |
| Min interval — too fast | `test_scheduler.py::test_min_interval_rejected_every_minute` | `* * * * *` → rejected with validation error |
| Min interval — adversarial | `test_scheduler.py::test_min_interval_adversarial_cron` | `*/1 0 * * *` → rolling week sampling detects 1-min gap in hour 0, rejected |
| schedule_enabled = False | `test_scheduler.py::test_schedule_disabled_not_triggered` | Source with valid cron but `schedule_enabled = False` → not triggered |
| sync_paused = True | `test_scheduler.py::test_paused_source_not_triggered` | Source with valid cron but `sync_paused = True` → not triggered |
| Migration — allowlist values | `test_migration_015.py::test_schedule_minutes_allowlist_converts_correctly` | 15, 30, 60, 1440 → correct cron expressions |
| Migration — non-allowlist nulled | `test_migration_015.py::test_schedule_minutes_non_allowlist_nulled_with_report` | 45, 90 → sync_schedule=NULL, schedule_enabled=False, report entry written |
| next_sync_at computed | `test_datasources_router.py::test_next_sync_at_returned_in_list` | GET /datasources/ returns correct `next_sync_at` for each three-state scenario |
| Preserve on toggle | `test_datasources_router.py::test_schedule_disabled_preserves_sync_schedule` | PATCH schedule_enabled=False → sync_schedule unchanged in DB |
