# SUPERVISOR.md — Operating Card for Scott

One-page field card for supervising a Claude session on this repo. You are the human in the loop; this tells you what to do, not what Claude does.

---

## 1. Before every session (30 seconds)

Skim these, in this order, so you can catch drift in real time:

1. `git log --oneline -10` — confirm the master tip matches what you expect. Current tip is post-v1.2.0 on `master` (Tier 5 + Tier 6 closed; docs sync landed at `f4c159a`, seed-file fix at `3cf7719`).
2. `CHANGELOG.md` top — `[Unreleased]` section tells you what has accumulated since v1.2.0 (2026-04-23). If `[Unreleased]` is empty and you expected changes, something was not committed.
3. `docs/UNIFIED-SPEC.md` header (first 20 lines) — canonical version is v3.1. "617 backend + 36 frontend tests" is the current truth line; any claim that differs is stale.
4. `docs/superpowers/specs/` — most recent file is the slice Claude is working on (if any). Read it before approving work.
5. `docs/CANONICAL-SPEC-GAP-LIST.md` + `docs/CHANGE-CONTROL.md` — if Claude proposes scope changes, these are the guardrails.

Red flag if any of these disagree with each other. Ask Claude to reconcile before proceeding.

---

## 2. During the session — what you actually do

1. **Demand evidence, not narration.** When Claude says "tests pass," ask for the raw tail. Backend is `docker compose run --rm api python -m pytest tests -q` (per `CLAUDE.md` Rule 1a) or `cd backend && pytest -q`. Frontend is `cd frontend && npm test -- --run`. Expect ~617 backend + 36 frontend passing.
2. **Run the sovereignty check yourself before a push.** `bash scripts/verify-sovereignty.sh`. No `verify-release.sh` exists in this repo — do not accept a claim that one was run.
3. **Check lint + types on touched code.** `cd backend && ruff check app tests`. `cd frontend && npx tsc --noEmit`. `cd frontend && npm run build` is the integrated check.
4. **Watch OpenAPI drift.** If backend schemas changed, `docs/openapi.json` must be regenerated and `frontend/src/generated/api.ts` refreshed via `npm run generate:types`. Zero-diff regen is the Tier-6 standard.
5. **Verify version lockstep before any push.** `backend/pyproject.toml` `version = "1.4.0"` must equal `frontend/package.json` `"version": "1.4.0"` must equal the top `[x.y.z]` entry in `CHANGELOG.md` must equal the "Current release" line in `docs/UNIFIED-SPEC.md`. A mismatch is a dealbreaker — no push.

---

## 3. Hard rules active on this project

Numbering matches `~/.claude/CLAUDE.md`. These fire hardest here:

- **Rule 9 — Documentation Gate.** All 6 artifacts must exist at push time: `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `LICENSE`, `.gitignore`, `docs/index.html`. A PreToolUse hook blocks `git push` with exit 2 if any is missing. This repo has an extended variant in its own `CLAUDE.md` Rule 0 (UML diagrams, README.{md,txt,docx,pdf}, USER-MANUAL three-section set, discussions seeded). Override phrase is literal: `override rule 9`.
- **Rule 10 — Subagent Obligation.** For any slice with 2+ non-overlapping scopes (backend + frontend + docs is the common shape here), Claude must dispatch parallel subagents. The 3rd distinct inline Edit/Write in a turn is blocked exit 2. Override is literal: `override rule 10`. This fires constantly on tier slices.
- **Rule 1 — Read before you write.** Before Claude edits `backend/app/*.py` or `frontend/src/*.tsx`, confirm the file was read in-session. Silent edits on unread files are the common failure mode.
- **Rule 2 — Run before you declare done.** "Tests should pass" is not done. Raw `pytest`/`vitest` output tail is done.
- **Rule 8 — Stay in scope.** Tier slices have locked boundaries (see `docs/CHANGE-CONTROL.md` and the Tier 5/6 memory entries). "Adjacent cleanup" is how scope expands. Reject unauthorized refactors.

---

## 4. Four-pass gate

See coder-ui-qa-test skill.

---

## 5. Good session ending — project-specific checklist

Work is done when ALL of these are true:

- [ ] Matches canonical v3.1 spec (`docs/UNIFIED-SPEC.md`); any divergence is documented in `docs/CHANGE-CONTROL.md`.
- [ ] `docker compose run --rm api python -m pytest tests -q` green, count at or above 617 backend tests (new work adds tests, never removes them).
- [ ] `cd frontend && npm test -- --run` green at or above 36 tests.
- [ ] `cd frontend && npm run build` succeeds (tsc + vite clean).
- [ ] `bash scripts/verify-sovereignty.sh` passes.
- [ ] Universal discovery/connection architecture (T2B/T3 connector + credentials model with `EncryptedJSONB` envelope on `data_sources.connection_config`) intact — no plaintext regression, single-key Fernet.
- [ ] Portal-mode switch still honors `private` default; `/auth/register` is 404 in private mode, mounted in public; `/config/portal-mode` always mounted.
- [ ] All 6 doc artifacts current (README.md, CHANGELOG.md, CONTRIBUTING.md, LICENSE, .gitignore, docs/index.html) plus the repo's extended set: README.{txt,docx,pdf}, USER-MANUAL.{md,docx,pdf}, `docs/architecture.mmd` + `docs/diagrams/`, `docs/github-discussions-seed.md`.
- [ ] Version in lockstep across `backend/pyproject.toml`, `frontend/package.json`, top of `CHANGELOG.md`, and UNIFIED-SPEC.md header.
- [ ] `docs/openapi.json` regen shows zero diff unless schemas genuinely changed; `frontend/src/generated/api.ts` matches.
- [ ] CI green on `master` — confirm via `gh run view --json conclusion` (public run page lags; gh API is authoritative per the 2026-04-23 finding).
- [ ] Working tree clean (`git status`), commit messages follow the `feat(tN)` / `fix(...)` / `docs:` / `chore(...)` convention visible in recent history.
