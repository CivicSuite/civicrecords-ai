# Finding — 404-vs-403 status code leaks dept-scoped resource existence

**Date:** 2026-04-19 (original finding) / 2026-04-20 (expanded scope during fix)
**Original trigger:** CI failure on PR #18 (`PATCH /requests/{id}/response-letter/{letter_id}` returned 404 instead of the expected 403) during the T2A-cleanup parameterized test.
**Severity:** Low–medium. Information disclosure, not an authorization bypass.
**Status:** **Fixed in the info-leak follow-up PR** (branch `ci/info-leak-fix-child-before-parent`). Scope expanded mid-fix after a codebase-wide audit; see "Scope expansion" below.

## The original pattern (child-before-parent)

Two handlers loaded a **child** resource by its ID and returned 404 if missing BEFORE loading the parent request and running the department access check. The 404-vs-403 difference at the child level let an authenticated cross-department caller distinguish "this child exists in another dept" (403) from "this child does not exist" (404).

| File | Function | Route | Fix |
|---|---|---|---|
| `backend/app/requests/router.py` | `update_response_letter` | `PATCH /requests/{id}/response-letter/{letter_id}` | **Reorder** — both IDs in path, so parent-request-load and dept-check now run before the letter lookup |
| `backend/app/exemptions/router.py` | `review_flag` | `PATCH /exemptions/flags/{flag_id}` | **Inline 404-unification** — only `flag_id` in path, so the flag must load first. Uses `has_department_access` inline and raises 404 "Flag not found" for every failure mode |

## Scope expansion — parent-level 404-vs-403 pattern

During the fix, a codebase-wide audit identified **the same 404-vs-403 disclosure at the parent level**. Every handler of the shape:

```python
req = await session.get(RecordsRequest, request_id)
if not req:
    raise HTTPException(404, "Request not found")
require_department_scope(user, req.department_id)   # raises 403 on cross-dept
```

…has the same info-leak on the parent `request_id`. Fake id → 404. Real-id-in-another-dept → 403. Status code distinguishes the two.

The audit found 21 handlers with this shape in `requests/router.py`, 2 in `documents/router.py`, and 2 in `exemptions/router.py` (`scan_for_exemptions`, `list_flags`). Same exposure level as the original child-before-parent case — a caller with a guessed/leaked UUID can probe for existence in another dept. UUIDs are 122-bit random so brute-force enumeration is infeasible, but leaked/shared IDs make the disclosure practical.

## The fix — `require_department_or_404` helper

Added `require_department_or_404(user, resource_department_id, detail)` in `backend/app/auth/dependencies.py` alongside `require_department_scope`. Same fail-closed rules, but raises **404** (not 403) on denial so the external response is identical to "resource does not exist".

```python
# backend/app/auth/dependencies.py
def require_department_or_404(user, resource_department_id, detail="Not found"):
    if not has_department_access(user, resource_department_id):
        raise HTTPException(status_code=404, detail=detail)
```

Every handler that previously called `require_department_scope(user, X.department_id)` was swapped to `require_department_or_404(user, X.department_id, "Request not found")` (or "Document not found" for document handlers).

`require_department_scope` stays in the codebase for use on surfaces where a semantic 403 is correct — e.g., admin-facing routes where the caller should know it's an authz issue, or analytics aggregates and list endpoints where there's no specific resource ID to probe.

## Attack model (before fix)

1. Attacker acquires a candidate resource UUID (from a leaked log, email, screenshot, prior legitimate context, or guessing if the ID is exposed via a URL)
2. Attacker sends a request with that UUID from their own authenticated account in a different department
3. Response is 404 → UUID is fake; 403 → UUID is real but in another department

For a FOIA product this reveals: "request X exists in another dept" / "letter Y attached to request X exists". Sensitive for some request topics.

## Scope (after fix)

**Fully 404-unified via `require_department_or_404`:**

| File | Call sites |
|---|---|
| `backend/app/requests/router.py` | 17 (GET/PATCH `/{id}`, attached documents, workflow, fees, response-letter, timeline, messages) |
| `backend/app/documents/router.py` | 2 (GET `/{id}`, GET `/{id}/chunks`) |
| `backend/app/exemptions/router.py` | 2 (POST `/scan/{request_id}`, GET `/flags/{request_id}`) |

**404-unified inline (non-raising helper):**

| File | Call sites |
|---|---|
| `backend/app/exemptions/router.py::review_flag` | 1 (PATCH `/flags/{flag_id}` — uses `has_department_access` inline because the flag must load first) |

**Intentionally left at 403 (semantic denial, no info-leak concern):**

- Every list endpoint (`GET /documents/`, `GET /analytics/operational`, `GET /requests/`) — no resource ID in path to probe; filters via WHERE clause; null-user-dept still raises 403 inline
- `backend/app/city_profile/router.py` — intentionally global singleton, admin-write only (per T2A design decision)
- `require_role(...)` role-gate 403s — unrelated to dept scoping

## Tradeoff — 404-unification vs semantic 403

Legitimate same-tenant users who mistype a resource ID now see "Not found" for both "does not exist" and "exists but you cannot access it." From a security standpoint this is the correct pattern — it's what most authz-sensitive REST APIs do (GitHub, Google Drive, Dropbox all unify on 404). From a UX standpoint it means a staff user who tries to open a colleague's request from another department gets no hint that it exists. Acceptable tradeoff: cross-department access was never a supported user path; a 403 would have disclosed structure the user wasn't authorized to learn about anyway.

## Regression tests

Three test files cover this:

**`backend/tests/test_info_leak_hardening.py`** (new, 6 tests, zero skips):
- `test_response_letter_patch_placeholder_letter_id_returns_404_cross_dept` — placeholder letter_id cross-dept → 404
- `test_response_letter_patch_real_letter_id_returns_404_cross_dept` — real dept-B letter_id cross-dept → 404
- `test_response_letter_patch_admin_still_works` — admin bypass → 200
- `test_review_flag_placeholder_id_returns_404` — baseline
- `test_review_flag_cross_department_returns_404_not_403` — real dept-B flag cross-dept → 404 with body "Flag not found"
- `test_review_flag_admin_still_works` — admin bypass → 200

**`backend/tests/test_tier2a_hardening.py`** (existing file, assertions flipped):
- Parameterized enforcement test asserts **404** (was 403) for every cross-dept case across 25 routes
- Individual documents/timeline/messages cross-dept tests assert 404

**`backend/tests/test_department_scoping.py`** (existing file, assertions flipped):
- `test_staff_gets_request_in_other_department_404` (renamed from `_403`) — cross-dept `GET /requests/{id}` → 404
- `test_reviewer_cannot_approve_other_department` — cross-dept workflow action → 404

## Second scope expansion — Pattern D list-endpoint fail-open

During review of the expanded-scope PR, the auditor flagged two request endpoints (`GET /requests/` and `GET /requests/stats`) that still fell open for non-admin users with `user.department_id is None`. The handler shape was:

```python
# BEFORE (fail-open on null user dept)
if user.role != UserRole.ADMIN and user.department_id is not None:
    stmt = stmt.where(RecordsRequest.department_id == user.department_id)
# else: no filter — null-dept non-admin sees every dept's rows
```

A codebase-wide sweep for this pattern found **4 affected handlers**, not 2:

| File | Handler | Route |
|---|---|---|
| `backend/app/requests/router.py` | `list_requests` | `GET /requests/` |
| `backend/app/requests/router.py` | `request_stats` | `GET /requests/stats` |
| `backend/app/search/router.py` | `execute_search` | `POST /search/query` |
| `backend/app/search/router.py` | `export_search_results` | `GET /search/export` |

### Fix — `require_department_filter` helper

Added in `backend/app/auth/dependencies.py`. Returns `None` for admin (no filter), raises 403 for non-admin with no department, returns `user.department_id` otherwise. The list/aggregate analog of `require_department_or_404` — for list endpoints there is no specific resource ID to probe, so a semantic 403 is correct.

```python
# AFTER (fail-closed)
dept_filter = require_department_filter(user)  # 403 if non-admin + null dept
if dept_filter is not None:
    stmt = stmt.where(RecordsRequest.department_id == dept_filter)
```

All 4 call sites converted. One additional reorder in `execute_search`: the dept check now runs BEFORE `session.add(SearchSession(...))` — a null-dept non-admin no longer writes a SearchSession row before the 403 fires.

### Regression tests

4 new tests in `backend/tests/test_tier2a_hardening.py`:

- `test_list_requests_denies_non_admin_with_null_department`
- `test_request_stats_denies_non_admin_with_null_department`
- `test_search_query_denies_non_admin_with_null_department`
- `test_search_export_denies_non_admin_with_null_department`

All four assert 403 from the `staff_token` fixture (non-admin, no department). No Ollama mock needed for search tests — the 403 fires before `hybrid_search` is ever called.

## Not in scope for this PR

- `/city-profile` — intentionally global, admin-write only. No dept scoping.
- Admin routes and role checks where 403 is semantically correct — unchanged.
