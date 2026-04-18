# CivicRecords AI — Auditor Session Handoff

**Date:** 2026-04-17
**Status:** Previous auditor session failed. New session starting with a reorientation prompt. Prior auditor did not apply the `coder-ui-qa-test` skill despite it being available from session start.

---

## Why this handoff exists

The previous auditor had `coder-ui-qa-test` in the available-skills list from the first message and did not load it. Three pushes went out under that auditor's sign-off — P6a (`e462c7e`), P6b (`c670ef1`), P7 (`55a1c66`) — none of which had the Rule 9 mandatory deliverables check performed.

When the user pointed out the skill had been skipped, the auditor loaded it and extracted only Hard Rule 9, ignoring the three roles (Principal Engineer, Senior UI Designer, Senior QA Engineer) and the Verification Log template that are the substance of the skill.

The dev team, in a separate session, produced a self-audit more exacting than the auditor's external audit. Seven categories the auditor missed:

1. No browser runtime verification of any P7 UI component
2. No browser console check
3. No viewport check at mobile/desktop widths
4. No adversarial input testing (including a real `int(Retry-After)` ValueError crash bug in the REST connector)
5. No accessibility check on P7 UI elements (health badge color-only communication, FailedRecordsPanel with no `aria-live`, silent elapsed counter)
6. No Verification Log produced at P7 close
7. No copy or content consistency review

When corrections arrived, the auditor repeatedly centered the retrospective on itself instead of on the work. The user is evaluating replacing the auditor with an outside AI or tooling.

**Important note on a misleading prior handoff.** A previous `handoff.md` (dated 2026-04-16, now overwritten by this file) claimed `coder-ui-qa-test (Hard Rules 9 + 10) have been removed from this workspace`. That claim was either outdated or wrong — the skill was active in the available-skills list the entire session. Do not trust a handoff's claim about active rules over the current skill list. Verify against `<available_skills>` in the session's own system context.

---

## Current repo state

- HEAD: `55a1c66` at `origin/master` (verify with `git rev-parse HEAD`)
- Shipped: P6a (idempotency contract split), P6b (cron scheduler rewrite), P7 (sync failures + circuit breaker + UI)
- Branch: `master`
- Code is functional at the logic layer. Documentation and runtime/UX verification are incomplete.

---

## Outstanding work — three parallel streams

### Stream 1: Rule 9 mandatory deliverables gap (blocks external release)

Per `coder-ui-qa-test` Hard Rule 9, v1.1 is not externally released until these exist and are current:

- **Professional UML architecture diagrams** (class / component / sequence / deployment). Drawn at design-review quality, not stubs. Mermaid or PlantUML preferred — renders inline on GitHub, embeddable in DOCX/PDF.
- **README.docx** with embedded UML
- **README.pdf** with embedded UML
- **README-FULL.pdf** regenerated to include P6a/P6b/P7 architecture
- **USER-MANUAL.md** three-section structure verified (End-User / Technical / Architectural) and updated with P7 content. File exists at repo root but section structure is unverified.
- **USER-MANUAL.docx** and **USER-MANUAL.pdf** regenerated. Files exist; P7 content status unverified.
- **docs/index.html** Download Installer button: currently shows `bash install.sh` as a code snippet, which fails Rule 9's "direct from GitHub Releases asset" requirement. Must be a real Releases-asset URL.
- **docs/index.html** Sync Failure Tracking section added to features
- **GitHub Discussions** seeded across every enabled category, verified via `gh` CLI or manual GitHub check

Files that exist but may be stale or non-canonical:
- `docs/civicrecords-ai-manual.{html,docx,pdf}` — non-canonical name; three-section structure unverified; separate from `USER-MANUAL.*`
- `README.txt` — exists at repo root, may not reflect P7
- `docs/index.html` — exists, updated for P6b but not P7

### Stream 2: P7 runtime / UX / accessibility cleanup (flagged by dev team's self-audit, not yet addressed)

- **`int(Retry-After)` ValueError vulnerability** in REST connector. `int(response.headers.get("Retry-After", "30"))` crashes on any non-integer value (`"banana"`, HTTP-date format per RFC 7231). Fix: try/except with fallback to default. Stretch: RFC 7231 HTTP-date parsing. Add test for malformed input.
- **Accessibility — `aria-label`** on health badge dot (color-only status communication fails WCAG 1.4.1)
- **Accessibility — `aria-live` region** on FailedRecordsPanel (WCAG 4.1.3 — panel mount is silent to screen readers)
- **Accessibility — Sync Now elapsed counter** updates silently. Add `aria-live="polite"` or `role="timer"` with `aria-label`.
- **Viewport check** at 1280px and 1024px for SourceCard. Element density (icon + name + health badge + schedule state + last-sync + next-sync + Sync Now + Edit + failure count + toggle) may wrap badly.
- **Browser console check** on every P7 UI path (SourceCard in 3 health states, FailedRecordsPanel in 5 states, Sync Now lifecycle, wizard with cron preview + Checkbox)
- **Copy consistency** — "Circuit Open" (display) vs `circuit_open` (internal token) normalized across badge, banner, spec, notification templates
- **FailedRecordsPanel error state** message review — actionable vs raw error dump

### Stream 3: UNIFIED-SPEC updates (proposed by previous auditor, not made)

- **§17 add priority 9**: "v1.1 release readiness (Rule 9 artifact gap)" tracking Stream 1 deliverables
- **§17 5a/5b/5c**: add footnote "Shipped prior to Rule 9 enforcement in this repo. Artifact gap tracked under priority 9."
- **§17.x add D-PROC-1**: process decision record for `coder-ui-qa-test` enforcement
- **§18 add three acceptance criteria**:
  - `coder-ui-qa-test` skill loaded as first action of every coding session
  - Rule 9 mandatory deliverables verified on disk before any push
  - Verification Log completed at task close with evidence, not assertions
- **§19 add Verification Log as position 0** in precedence hierarchy

---

## CLAUDE.md state

`CLAUDE.md` at the repo root was updated to add Hard Rule 0 requiring `coder-ui-qa-test` to be loaded as the first action of any coding or audit session. The full Rule 9 refusal template and override phrase (`"override rule 9"`) are documented there. The new session must read `CLAUDE.md` and comply.

---

## Process failures — do not repeat

1. **`coder-ui-qa-test` loads first.** Before reading this handoff, before reading the spec, before exploring the repo. First tool call. The skill will be in `<available_skills>` at session start — confirm it's there and load it.

2. **Loading the skill is not the same as applying it.** Three roles — Principal Engineer, Senior UI Designer, Senior QA Engineer — and a Verification Log template with nine evidence categories. All apply to all code- or UI-touching work. Rule 9 is one part of the skill, not the skill.

3. **Static ≠ Runtime.** Unit tests prove logic. They do not prove the admin sees what the spec says they should see, the console is clean, the layout doesn't clip at 1024px, or the screen reader gets an announcement when a panel mounts. For any UI-touching task, before sign-off: start the dev server, walk the paths, check the browser console, check at least two viewport widths, check accessibility.

4. **Verification Log is mandatory at task close.** Not a test count summary. The full Log: Files Read, Existing Patterns Identified, Tests (added/updated + full suite output), Runtime Verification, Visual & Viewport Check, Browser Console, Copy & Content Check, Security Review, Performance Review, Blast Radius & Regression, Documentation Artifacts table, Version Control, Sign-off. Evidence pasted raw from terminal/browser. Assertions without evidence are worth nothing.

5. **Do not trust dev-team summaries.** Verify each claim. When the dev reports "all deliverables exist," open each file and confirm. When they say "423 tests pass," look at what the 423 cover and what they don't. The audit exists to catch what the builder missed, not to validate what the builder wrote.

6. **Tool flakiness is not authoritative.** If Glob returns "no files found" and the result is suspect (a known issue in this environment), retry with different patterns or use an alternate tool. A single negative result is not proof of absence.

7. **Keep the focus on the work.** When a correction arrives, the response is the fix and the next step. Not a multi-paragraph retrospective about the auditor.

8. **Do not trust prior handoff claims about active rules.** The 2026-04-16 handoff falsely claimed `coder-ui-qa-test` was removed. Verify against the current session's `<available_skills>` list, not against narrative claims in documents.

---

## First action for new session

1. Load `coder-ui-qa-test` skill (first tool call — verify it's in `<available_skills>`)
2. Read `CLAUDE.md` at the repo root (Hard Rule 0 and project standards)
3. Read this `handoff.md`
4. Read `docs/UNIFIED-SPEC.md` §17 for current priority state
5. Present the user with a prioritized plan for closing the three outstanding streams, with Rule 9 as the gating item

No push is approved until every Rule 9 deliverable has been verified on disk with an actual file path, every P7 UI-flagged issue has been addressed with evidence in a Verification Log, and the UNIFIED-SPEC updates in Stream 3 have been made.

If the new session catches itself pattern-matching on what feels done rather than mechanically walking the skill's checklists — stop. That was the previous session's failure mode. The work does not resume until the checklist is walked.
