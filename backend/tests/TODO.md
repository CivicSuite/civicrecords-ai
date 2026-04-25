# backend/tests follow-ups

Items deferred from past PRs. Each entry names the originating PR/audit and a rough scope so a future contributor can pick it up cleanly.

## Gate 2 follow-ups (deferred from Step 2b — Gate 2 fixture upgrade, 2026-04-24)

- **Data-preservation assertion in `test_gate2_upgrade_from_v1_2`.** The current Gate 2 verifies the schema upgrade path (DDL idempotency, head stamping, column preservation) but does NOT seed rows into shared tables (`users`, `audit_log`, `documents`) before the upgrade and verify they survive. A real operator at v1.2.0 has data, not just an empty schema. Adding seed-and-verify rows would prove the upgrade preserves user data, not just structure. Out of scope for the v1.3.0 release because it's a stronger gate, not a fix for an existing one.
