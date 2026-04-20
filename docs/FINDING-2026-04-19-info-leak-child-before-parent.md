# Finding — child-before-parent 404 leaks resource existence

**Date:** 2026-04-19
**Surfaced by:** CI failure on PR #18 (`PATCH /requests/{id}/response-letter/{letter_id}` returned 404 instead of the expected 403) during the T2A-cleanup parameterized test.
**Severity:** Low–medium. Information disclosure, not an authorization bypass.
**Status:** **Fixed in the info-leak follow-up PR** (fix commit on branch `ci/info-leak-fix-child-before-parent`, merged 2026-04-20). This doc lands with that PR as the durable record.

## The pattern

Two handlers in the codebase loaded a child resource by its ID and returned 404 if missing BEFORE loading the parent request and running the department access check. This ordering let any authenticated staff user distinguish "this child exists but I can't access it" from "this child does not exist" by watching the 404-vs-403 difference.

## Confirmed call sites (both now fixed)

| File | Function | Route | Line (original) | Fix pattern |
|---|---|---|---|---|
| `backend/app/requests/router.py` | `update_response_letter` | `PATCH /requests/{id}/response-letter/{letter_id}` | 1158 | **Reorder** — both IDs are path params, so load parent request + dept-check before the letter lookup |
| `backend/app/exemptions/router.py` | `review_flag` | `PATCH /exemptions/flags/{flag_id}` | 319 | **404-unification** — only `flag_id` is in the path, so the flag must load first to resolve its parent. Every failure mode (missing flag, missing parent request, cross-department) returns the same 404 "Flag not found" |

The two handlers needed different fix patterns because their URL shapes differ. The original version of this finding claimed both could be fixed by a straight reorder — that was incorrect for `review_flag` (the flag must load first to know the parent request). Corrected here.

## Attack model

An adversary with any STAFF-or-higher account in any department could:

1. Acquire a candidate child UUID (e.g. from a leaked log, email, screenshot, or a prior legitimate context in the same tenant)
2. Send PATCH with that child UUID
3. Response is 404 → ID is fake; 403 → ID is real but in another department

UUIDs are 122-bit random so brute-force enumeration is not viable. The defect applied when a specific ID was leaked or targeted.

## Fix 1 — `update_response_letter` (reorder)

Both `request_id` and `letter_id` are path parameters, so we can load the parent request first without needing the letter. This fully closes the leak — the dept check fires before any child-existence check runs.

```python
# BEFORE (broken)
letter = await session.get(ResponseLetter, letter_id)
if not letter or letter.request_id != request_id:
    raise HTTPException(404, "Response letter not found")

req = await session.get(RecordsRequest, request_id)
if not req:
    raise HTTPException(404, "Request not found")
require_department_scope(user, req.department_id)

# AFTER (closed — reorder)
req = await session.get(RecordsRequest, request_id)
if not req:
    raise HTTPException(404, "Request not found")
require_department_scope(user, req.department_id)

letter = await session.get(ResponseLetter, letter_id)
if not letter or letter.request_id != request_id:
    raise HTTPException(404, "Response letter not found")
```

## Fix 2 — `review_flag` (404-unification)

The URL is `/flags/{flag_id}` — only `flag_id` is in the path. The handler has no way to know the parent request without first loading the flag. Reorder is structurally impossible.

The fix is to make the external response uniform across all three failure modes: flag missing, parent request missing, or cross-department. All three return 404 "Flag not found" so the caller cannot distinguish via status code or body text.

This required a new non-raising helper `has_department_access` (added in `backend/app/auth/dependencies.py` alongside `require_department_scope`) so the handler could branch on access without catching the 403 that `require_department_scope` raises.

```python
# BEFORE (broken + had a separate latent fail-open)
flag = await session.get(ExemptionFlag, flag_id)
if not flag:
    raise HTTPException(404, "Flag not found")

# Department check via the flag's request
req = await session.get(RecordsRequest, flag.request_id)
if req:
    require_department_scope(user, req.department_id)
# NOTE: if req is None (orphan flag), the dept check was silently skipped
# and the handler proceeded to mutate the flag. That's a separate bug.

# AFTER (closed — 404-unification, also fixes the orphan-flag fail-open)
flag = await session.get(ExemptionFlag, flag_id)
req = await session.get(RecordsRequest, flag.request_id) if flag else None
if not flag or not req or not has_department_access(user, req.department_id):
    raise HTTPException(404, "Flag not found")
```

The prior `if req:` guard silently skipped the dept check when a flag referenced a missing request (data-integrity edge case). The rewrite also closes that fail-open — any missing parent now returns 404 uniformly.

## Tradeoff of 404-unification

Legitimate same-tenant users who mistype a flag_id now see "Flag not found" for both "does not exist" and "exists but you cannot access it." From a security standpoint this is correct. From a UX standpoint it means a staff user who tries to open a colleague's flag from another department gets no hint that it exists — they just see 404. Documented tradeoff; not considered a UX regression because cross-department flag access was never a supported path.

## Regression tests

`backend/tests/test_info_leak_hardening.py` (new) contains 6 tests:

| Test | Asserts |
|---|---|
| `test_response_letter_patch_placeholder_letter_id_returns_403_cross_dept` | Cross-dept caller with a placeholder (non-existent) letter_id gets 403, not 404. Proves the info-leak is closed for this handler. |
| `test_response_letter_patch_real_letter_id_returns_403_cross_dept` | Cross-dept caller with a real dept-B letter_id still gets 403. Regression guard. |
| `test_response_letter_patch_admin_still_works` | Admin can PATCH any dept's letter. Over-correction guard. |
| `test_review_flag_placeholder_id_returns_404` | Placeholder flag_id returns 404. Baseline. |
| `test_review_flag_cross_department_returns_404_not_403` | Real dept-B flag accessed cross-dept returns 404 (not 403) with body "Flag not found". Proves the 404-unification. |
| `test_review_flag_admin_still_works` | Admin can review any dept's flag. Over-correction guard. |

Zero test skips. Zero xfails.

## Not in scope for this PR

- `PATCH /exemptions/flags/{flag_id}` was intentionally NOT in the parameterized enforcement test in `test_tier2a_hardening.py` because the test covers 403-on-cross-dept and this handler now returns 404-on-cross-dept. Adding it to the parameterized list would require the test to special-case two different expected status codes per row. Kept separate in `test_info_leak_hardening.py` where the 404 expectation is explicit.
- Other handlers that might have similar child-before-parent patterns: grep-verified none. Only these two existed in `backend/app/`.
