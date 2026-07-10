# CivicSunshine B2 Phase 2 Rehearsal

Date: 2026-05-11
Branch: master
Master HEAD: 5e7425dc7a226f63a4ba8a91aa76cb30491c03ef
Phase 1 PR: #74
Phase 1 merge SHA: 902db173366359124e4d8e84f3c440df61aa62f4
Phase 1B PR: #76
Phase 1B merge SHA: 5e7425dc7a226f63a4ba8a91aa76cb30491c03ef
Status: Phase 2 GREEN - halt at human v1.6.0 tag-push approval gate

## Goal

Run the B2 Docker secret extraction rehearsal before any v1.6.0 tag push:

- release verifier
- live API-container env proof
- B2 contract test
- backend collect-only count
- no tag push

## Command Environment Note

PowerShell's default `bash.exe` resolves into WSL through a Docker bind-mount
path, which gives Docker Compose a hashed project name and can reuse a stale
project-specific image. The successful rehearsal used Git Bash from the Windows
working tree:

```text
C:\Program Files\Git\bin\bash.exe scripts/verify-release.sh
```

Before the successful run, both the normal and WSL-hash Compose projects were
stopped and the API image was rebuilt from the merged master tree.

## Release Verifier Output

```text
RECOVERY-GATES: PASSED
SECRET-SCAN: PASSED (510 tracked file(s) scanned)
[PASS] compose runtime provisioned
[PASS] api container env hides JWT_SECRET and FIRST_ADMIN_PASSWORD (literal directive grep)
DATA SOVEREIGNTY: PASSED WITH WARNINGS
[PASS] sovereignty guard passed
[PASS] one unique version across 4 surface(s)
[PASS] required docs present
[PASS] ruff: 0 violations
[PASS] pytest collect-only: 638 test(s)
[PASS] pytest full suite: 638 passed
[PASS] frontend vitest
Test Files 9 passed (9)
Tests 36 passed (36)
[PASS] frontend production build
[PASS] Playwright user-flow tests
4 passed
RUNTIME-INSTALL-PROOF: health {'status': 'ok', 'version': '1.6.0'}
RUNTIME-INSTALL-PROOF: PASSED
[PASS] runtime install proof
VERIFY-RELEASE: PASSED
```

## Literal B2 Env-Grep Acceptance Proof

Command:

```bash
docker compose exec -T api env | grep -E 'JWT_SECRET|FIRST_ADMIN_PASSWORD'; echo exit=$?
```

Output:

```text
exit=1
```

Interpretation: zero matching env names are visible in the running API
container. This satisfies the literal B2 criterion from the directive.

## Contract Test Proof

Command:

```bash
docker compose run --rm api python -m pytest tests/test_docker_secret_contract.py -v
```

Output:

```text
tests/test_docker_secret_contract.py::test_env_example_declares_no_b2_secret_env_names PASSED
tests/test_docker_secret_contract.py::test_compose_mounts_secrets_via_docker_secret_block PASSED
tests/test_docker_secret_contract.py::test_release_gate_uses_literal_directive_grep PASSED
3 passed in 0.04s
```

The first assertion would have failed if `.env.example` still declared
`JWT_SECRET_FILE=` or `FIRST_ADMIN_PASSWORD_FILE=`.

## Collect-Only Proof

Command:

```bash
docker compose run --rm api python -m pytest tests --collect-only -q | tail -5
```

Output:

```text
638 tests collected in 1.62s
```

## Tag-Move Table

| Tag | Initial SHA | Final SHA | Moves | Notes |
| --- | --- | --- | --- | --- |
| v1.6.0 | not pushed | not pushed | 0 | tag push awaiting Scott approval |

## Stop Point

No tag has been pushed. Awaiting human tag-push approval gate.
