# CivicRecords AI - Remediation Plan

**Date:** 2026-04-19  
**Scope:** Merge the two audit streams into one execution plan for current `master` without overstating what is already proven.  
**Status:** Drafted for execution sequencing, not final sign-off.

---

## Ground Rules

1. The combined severity counts from the two audits are **provisional until re-verified against current HEAD**.
2. No tier is considered complete just because code lands. Every tier has merge gates and re-verification gates.
3. CI lands before substantive fixes so the rest of the work has a ratchet against regression.
4. Security and auth/authz fixes come before product-surface cleanup.
5. Root-cause fixes are preferred over one-off patching when the scope is still manageable.

---

## Current Combined Picture

The two audits overlap on:

- connector taxonomy drift
- first-boot truth gap
- landing-page and docs truth drift
- public-role overreach

They are complementary on security:

- the audit-team stream surfaced several auth/authz and response-shape risks
- the standard audit surfaced the embedded GitHub token, placeholder admin password acceptance, and broader bootstrap/release-truth drift

### Important caution on counts

Do **not** lock the project plan to "8 Blockers and 7 Criticals" as settled fact yet. Some findings were observed on different commits, some were inferred from static reading, and some need current-HEAD runtime repro before their final severity should be treated as binding.

Use this plan to sequence remediation. Use current-HEAD re-verification to finalize severity and closure.

---

## Re-Verification Pass Before Tiering

Before starting any code-fix tier beyond token rotation, do one short confirmation pass on current HEAD:

- re-check every alleged Blocker and Critical against current code
- classify each as:
  - `Confirmed on current HEAD`
  - `Likely still real but not yet runtime-verified`
  - `Historical / already fixed`
- capture one-line evidence for each in a working checklist

This keeps the plan honest and prevents spending a week sequencing already-closed findings as if they were still open.

---

## Tier 0 - Immediate Containment

### T0.1 - GitHub token: scoped acceptance, not rotation

**Decision (owner, 2026-04-19):** The PAT in the local `.git/config` remote URL is **not** being rotated. The token stays in the local remote config. The owner has accepted the local-exposure risk (screen share, backups of `.git/`, filesystem access on this machine). Git does not push `.git/config` to the remote, so the token does not reach public GitHub through normal push operations.

Scope of what is still required (local-only, read-only):

- grep remote git history to confirm the token was never committed into tracked files (defensive sweep — catches accidental `git add .git/` or tokenized URLs pasted into docs/install scripts)
- grep working tree for the token string across all tracked files
- grep HANDOFF.md, install.sh, install.ps1, and any operational docs for tokenized URLs
- if any finding above is positive, escalate to the owner before any rewrite

Merge gate:

- no findings in history or working tree (or findings surfaced to owner and resolved by owner's explicit call)

Verification gate:

- grep output pasted in Verification Log under `[AUDITOR-RUN]`
- local remote URL unchanged (token preserved per owner decision)

Estimated effort: under 15 minutes

---

## Tier 1 - Ratchet First

### T1.1 - Land CI as PR 0

This PR lands alone.

Why first:

- every downstream fix is reversible without CI
- prior audit failures already proved the repo can drift far from claimed test truth

CI baseline should include:

- backend test collection
- backend test run
- frontend test run
- frontend build
- generated-artifact drift checks where practical

Nice-to-have checks can follow later, but the basic ratchet must land now.

Merge gate:

- required CI workflow exists under `.github/workflows/`
- branch protection or equivalent required-check discipline is configured

Verification gate:

- introduce a deliberate failing test on a throwaway branch and confirm CI blocks merge

Estimated effort: 1 day

---

## Tier 2 - Security and Authorization Core

These issues are tightly related, but this tier should be split into smaller PRs so review quality stays high.

### T2A - Auth/Authz PR

Scope:

- introduce `UserSelfUpdate` schema (subset of `UserUpdate` with `role` and `department_id` removed); route `PATCH /users/me` to the narrower schema so a STAFF JWT patching `{"role": "admin"}` is rejected at validation, not at business logic
- create a `require_department_scope(user, resource_dept_id) -> None | raises 403` FastAPI dependency that fails closed: `if user.department_id is None and user.role != "admin": raise 403`
- apply the dependency to `backend/app/documents/router.py` (currently unscoped), `backend/app/analytics/router.py`, messages, timeline, and city-profile routes
- add a parameterized test `test_mutating_endpoints_enforce_department_scope` that iterates over every non-public route using the existing `staff_token_dept_a` / `staff_token_dept_b` fixtures

Why first in Tier 2:

- these are the highest-risk user-to-admin or cross-department exposure paths
- the `check_department_access` primitive already exists and is tested — this is a centralization and rollout job, not new logic

Merge gate:

- explicit regression tests for self-escalation (PATCH /users/me with role field) and for cross-department access on every newly scoped route
- the parameterized enforcement test exists and covers every mutating endpoint

Verification gate:

- attempts to cross department boundaries or self-escalate fail on current branch under `[AUDITOR-RUN]` conditions

Estimated effort: 2-3 days

### T2B - Sensitive Data Exposure PR

Scope:

- introduce `DataSourceRead` (redacted: no `connection_config`, no credential fields) and `DataSourceAdminRead` (full shape, admin-only) in `backend/app/datasources/schemas.py`; route `GET /datasources/` to the redacted shape by default and guard the admin shape behind an admin-role dependency
- sweep every user-visible response schema under `backend/app/*/schemas.py` for secrets, connection strings, tokens, OAuth client secrets, internal-only fields; document findings in a checklist that ships with the PR
- add response-shape assertion tests: for each affected endpoint, assert STAFF response bodies do not contain any key in a declared "sensitive fields" list (e.g. `connection_config`, `api_key`, `token`, `password`, `client_secret`, `database_url`)

**Important scope limit — this PR does not close ENG-001 by itself.** Response-shape redaction prevents credentials from reaching non-admin users at runtime. It does not prevent credentials from reaching operators who can read the database directly: DB backups, pg_dump outputs, restored snapshots, and any Postgres superuser session all still show plaintext `connection_config`. At-rest encryption for `data_sources.connection_config` is the companion fix — it is scoped to Tier 6 today, and **ENG-001 should not be marked fully closed until Tier 6 lands**. T2B's closure note must say "runtime exposure closed; storage exposure tracked in Tier 6."

Why separate:

- response-shape review is security-critical but mechanically different from authz logic
- easier to review and easier to prove exhaustively

Merge gate:

- response schema audit checklist completed and committed in the PR
- regression tests asserting redaction for non-admin roles
- T2B closure note explicitly distinguishes runtime exposure (closed) from storage exposure (still open, Tier 6)

Verification gate:

- non-admin responses do not expose sensitive connection/config fields under `[AUDITOR-RUN]` conditions
- auditor confirms ENG-001 status is recorded as "runtime closed / storage open" rather than "closed"

Estimated effort: 1-2 days

### T2C - Bootstrap and Connector Surface Hardening PR

Scope:

- extend `backend/app/config.py` startup validation (currently rejects insecure `JWT_SECRET`) to also reject a placeholder `FIRST_ADMIN_PASSWORD`: fail fatally if it matches the `.env.example` value, is empty, is shorter than 12 chars, or matches a short embedded blocklist; update `.env.example` and both installers (`install.sh`, `install.ps1`) to either prompt for a real password or generate one
- add a SSRF/target-validator for admin-configurable connector URLs (REST, ODBC): reject `127.0.0.0/8`, `169.254.0.0/16` (IMDS), `::1`, `localhost`, `0.0.0.0`, and RFC1918 ranges by default at schema-validation time; provide an explicit env-configured allowlist for on-prem internal services so air-gapped deployments can still reach legitimate internal hosts
- unit-test each blocked range and the allowlist mechanism
- add an integration test that confirms a fresh `docker compose up` with a placeholder admin password fails to start

Why separate:

- startup/config validation and connector-network policy are related but should not be hidden inside larger auth changes
- these are mechanically different from response-shape work and have their own review surface

Merge gate:

- startup fails on placeholder admin password (test asserts)
- connector validation tests exist for every blocked range, plus an allowlist-override test

Verification gate:

- fresh-start bootstrap with placeholder password fails fatally under `[AUDITOR-RUN]` conditions
- blocked connector destinations (IMDS, loopback, RFC1918 by default) are rejected deterministically

Estimated effort: 1-2 days

Tier 2 must be fully merged before Tier 3 begins.

---

## Tier 3 - Contract Drift and Admin Onboarding

This tier attacks the root cause behind several repeated failures: frontend/backend contract drift.

### T3A - Fix admin user creation path

Scope:

- point Users UI at the real admin-create endpoint
- verify current route contract

Merge gate:

- component test for correct endpoint

Verification gate:

- admin create-user flow succeeds against live backend

Estimated effort: less than 1 day

### T3B - Connector taxonomy unification

Scope:

- define one canonical connector/source-type vocabulary in a single source file (suggested: `backend/app/connectors/types.py`) — every other layer imports or mirrors from it
- align `backend/app/models/document.py` DB enum (with Alembic migration), `backend/app/connectors/__init__.py` registry keys, `backend/app/ingestion/tasks.py` worker dispatch, `frontend/src/pages/DataSources.tsx` chooser options + submit payload, README, landing page, and UNIFIED-SPEC
- decide per connector whether it is:
  - implemented — ships normally
  - stub/planned — removed from the chooser for this release, or rendered as a visibly `disabled` option with a "Coming in v1.2" tooltip
  - removed — dropped from UI, enum, docs, and roadmap together

**Non-negotiable rule for this sub-PR:** no connector value ships in the UI chooser unless it is backed by an implemented, tested, persistable, and runnable backend path. A chooser value that succeeds on create and fails silently on first sync is worse than no chooser value at all. If in doubt, disable it with a clear roadmap label.

Why important:

- this is one of the clearest shared findings across both audits
- the stub-vs-implementation question is what determines whether this is a naming fix or a build-from-scratch task

Merge gate:

- single canonical type definition exists and is imported/mirrored everywhere
- every UI option either (a) maps to a persistable and runnable backend path, or (b) is rendered as explicitly disabled with roadmap labeling
- no chooser value exists that would fail on first sync

Verification gate:

- create/test/list flow for every advertised connector type

Estimated effort: 2-3 days depending on scope decisions

### T3C - Test Connection truthfulness

Scope:

- ensure full REST/ODBC config is actually submitted
- return actionable validation and runtime failures

Merge gate:

- request payload tests for full config submission

Verification gate:

- UI test-connection path proves the same config that persistence will use

Estimated effort: 1 day

### T3D - OpenAPI typegen

Scope:

- generate frontend types from backend OpenAPI
- migrate the most drift-prone pages first
- add CI diff check

Why here:

- this is the root-cause fix for the class of bugs T3A-T3C belong to

Merge gate:

- generated types are part of the workflow
- CI fails on stale generated types

Verification gate:

- target pages compile against generated types only

Estimated effort: 1-2 days

Tier 3 must be fully merged before Tier 4 begins.

---

## Tier 4 - UI Runtime and Accessibility

This tier is for high-value user-facing fixes that affect first impression, operability, and trust.

### T4A - Responsive AppShell

Scope:

- collapsible or drawer-based sidebar below desktop widths
- keyboard-safe interaction model

Merge gate:

- browser evidence at mobile, tablet, desktop widths

Verification gate:

- app is usable below 1024px without layout lock-in

Estimated effort: 1-2 days

### T4B - Status/runtime contract fixes

Scope:

- `/admin/status` shape alignment if still broken
- service status indicators reflect actual backend truth

Important note:

- if this is breaking real admin flows, it can be pulled earlier into Tier 3

Merge gate:

- tests use real contract shape

Verification gate:

- healthy stack renders healthy indicators

Estimated effort: 1 day

### T4C - Error handling and form accessibility pass

Scope:

- replace raw/unhelpful UI errors with categorized actionable errors
- associate labels properly
- fix obvious dead CSS classes or inconsistent control styling where found

Merge gate:

- accessibility checklist for touched forms

Verification gate:

- browser + axe or equivalent pass on changed flows

Estimated effort: 1-2 days

---

## Tier 5 - First-Boot Truth and Release Truth

This tier cleans up the false story around install, onboarding, and what the repo actually ships.

### T5A - Onboarding persistence truth

Scope:

- make the onboarding interview actually persist what it claims to persist
- align tests to truthful behavior

Estimated effort: 1 day

### T5B - Seeding/bootstrap truth

Scope:

- decide whether required seeds happen automatically or through an explicit enforced step
- eliminate silent unseeded states

Estimated effort: 1-2 days

### T5C - Ollama/model truth

Scope:

- align installer behavior, runtime defaults, and product claims
- decide between:
  - installer pulls required models
  - default model changes
  - in-app health-gated model readiness

Estimated effort: 1-2 days

### T5D - Docs and landing page truth

Scope:

- fix broken commands and links
- fix overstated install/readiness claims
- fix 11-versus-10 status drift and generator discipline
- remove or defer public-role/public-portal claims if the feature is not shipped

Merge gate:

- all user-facing docs tell one truthful story

Verification gate:

- every published link and command is validated from the surface where users actually see it

Estimated effort: 2-3 days

Tier 5 closes the remaining Critical-class truthfulness work before release.

---

## Tier 6 - Watchlist / Next Sprint

Not required for the first remediation release unless new evidence raises severity:

- at-rest encryption for sensitive datasource config
- dedicated migration/init flow instead of app-start migrations
- browser E2E smoke coverage
- forced password rotation on first login
- bundle-size work
- upload hardening
- dependency scanning expansion
- federation and transparency-layer roadmap work

---

## Suggested Release Target

For a single focused developer:

- Tier 0: same day
- Tier 1: day 1
- Tier 2: days 2-6
- Tier 3: days 6-10
- Tier 4: days 10-13
- Tier 5: days 13-18

Working estimate for a truthful `v1.1.1` remediation release with Blockers and Criticals closed: **about 3 weeks**.

That estimate assumes:

- Tier 2 issues are mostly confirmed as still real on current HEAD
- connector decisions are made quickly
- no hidden migration or deploy surprises appear

---

## Merge Gates By Tier

No tier advances until the previous tier is both merged and re-verified.

### Global gates for every tier

- new or updated tests exist for changed behavior
- CI is green
- changed docs are updated in the same tier when user-visible behavior changes
- verification log entries are produced for runtime/UI changes

### Extra gates

- Tier 1 must establish the ratchet
- Tier 2 must prove auth/authz and sensitive-data fixes
- Tier 3 must prove contract unification and stop shipping broken admin onboarding
- Tier 4 must include browser evidence
- Tier 5 must make the product story truthful across installer, runtime, and docs

---

## Decisions Needed Before Tier 3 / Tier 5

1. Which connector types are truly implemented today, which are stubs, and which should be disabled instead of advertised?
2. What is the intended Ollama truth for first boot: pull more models, change defaults, or health-gate the feature?
3. Is the `Public` role being removed from this remediation release and deferred to a later portal milestone?

---

## Recommended Next Move

Start with:

- Tier 0 immediately
- Tier 1 immediately after
- short current-HEAD re-verification pass before Tier 2 coding begins

That keeps the plan honest, prevents overfitting to stale findings, and puts the ratchet in place before the expensive fixes start.
