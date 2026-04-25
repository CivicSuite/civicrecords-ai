# ADR-0004: Phase 2 — civiccore.llm extraction architecture

- **Status:** Accepted
- **Date:** 2026-04-25
- **Deciders:** Scott (product owner / final authority), records-ai dev team
- **Supersedes:** none
- **Superseded by:** none
- **Related:** ADR-0003 (Phase 1 CivicCore extraction baseline — migration gates 1/2/3, two-layer Alembic order, idempotency-guard pattern)

---

## 1. Context

Phase 1 (ADR-0003) extracted the shared identity and audit surface (`User`, `Role`, `Department`, `audit_log`) into the `civiccore` package and shipped records-ai v1.3.0 against `civiccore` v0.1.0 as a versioned wheel dependency. Phase 1 is **closed** — followups are release-hardening, never "Phase 1 v2".

Phase 2 lifts the next layer of suite-wide concern: **LLM provider abstraction and prompt template ownership**. Three forces drive the timing:

1. **A second consumer is imminent.** `civicclerk` (the meeting-management sibling product) is about to scaffold and will need the same provider/prompt machinery records-ai has. Scaffolding `civicclerk` against records-ai's private LLM module would re-create the exact coupling that Phase 1 just dissolved.
2. **records-ai's `app.llm` package is already the "would-be civiccore" shape.** `app/llm/client.py` exposes a single async `generate()` against Ollama; `app/llm/context_manager.py` carries token-budget + sanitization logic; `model_registry` and `prompt_templates` are already records-side tables. The extraction is unblocking the design rather than inventing it.
3. **civiccore is currently a clean foundation.** The post-Phase-1 surface area is small (4 shared models, 1 migration runner, 1 guards module). Adding `civiccore.llm` now — before more consumers exist and before more records-side code grows around the current LLM client — is materially cheaper than later.

The civicclerk scaffold is the deadline. Phase 2 must close before civicclerk's first migration lands.

---

## 2. Decision

Extract LLM provider abstraction, prompt template management, and the model registry into `civiccore.llm`. Records-ai consumes them via `civiccore` v0.2.0 with an override capability for prompt templates.

**Six locked architecture decisions** (set at sprint kickoff; not relitigated in this ADR):

1. **Prompt templates: civiccore-owned with records-ai override capability.** The `prompt_templates` table moves to civiccore; consumers register defaults under their own `consumer_app` namespace and may override at runtime.
2. **Provider clients: pluggable ABC from day one.** A single `LLMProvider` ABC in `civiccore.llm.providers` with concrete impls for Ollama (records-ai's current backend), OpenAI, and Anthropic shipped in v0.2.0.
3. **No cost tracking, no budget enforcement.** The token-counting utility (`estimate_tokens`, `assemble_context`, `TokenBudget`) ports as-is. No spend ledger, no per-tenant cap — out of scope.
4. **Shared tables: 16 → 18.** `model_registry` and `prompt_templates` move to civiccore. The `civiccore_0002_llm` migration creates them.
5. **civiccore version target: v0.2.0.** Minor bump (new module surface, no breaking changes to v0.1.0 consumers).
6. **Gate 2 fixture captured from v1.3.0 tag.** New `backend/tests/fixtures/schema_v1_3_0.sql` replaces `schema_v1_2_0.sql`; gate test renamed accordingly.

---

## 3. Migration order (post-Phase-2)

The two-layer pattern from ADR-0003 is preserved. The runner-subprocess invocation in `backend/alembic/env.py` already calls `civiccore.migrations.runner.upgrade_to_head()` BEFORE records-side migrations run; that wiring is unchanged. What changes is what civiccore's runner does:

```
1. civiccore baseline (Phase 1, unchanged): creates User, Role, Department, audit_log,
   alembic_version_civiccore tracking row.

2. NEW: civiccore_0002_llm: creates model_registry and prompt_templates with the
   civiccore-owned shape (consumer_app column, override-resolution columns described
   in §6). Stamps alembic_version_civiccore to revision 0002.

3. records-ai chain: runs as before. Records-side migrations that historically
   created or modified model_registry / prompt_templates now no-op idempotently
   (see §4).
```

**Operator-visible change:** none on fresh install (civiccore runs first end-to-end). On upgrade from v1.2.x or v1.3.0, the records-side migrations that previously owned these tables become no-ops on second-or-later upgrades (the first upgrade is the handoff: civiccore creates the table; the records-side migration sees `has_table` and skips).

---

## 4. Idempotency-guard pattern for new shared tables

Same `if has_table` / `if column_exists` / `if constraint_exists` pattern Phase 1 used for the 14 guarded migrations. The Phase 2 audit must add guards to records-side migrations that touch the two newly-shared tables.

**Records-ai migrations requiring guards added in this sprint:**

- `backend/alembic/versions/003_model_registry.py` — currently creates `model_registry` via `idempotent_create_table` (already guarded — Phase-1-style guard suffices; no change needed beyond confirming the guard's `has_table` shortcut path is exercised post-extraction).
- `backend/alembic/versions/787207afc66a_phase2_extensions_12_new_tables_and_.py` — Phase 2 records-side migration that references `model_registry` and `prompt_templates`. Audit each `op.create_table`, `op.add_column`, and `op.create_foreign_key` call against these two tables; wrap any unguarded statement in the `column_exists` / `constraint_exists` helpers from `civiccore.migrations.guards`.

(The exhaustive list will be confirmed by the Step 3 implementer via `git grep -l 'model_registry\|prompt_templates' backend/alembic/versions/`. The two files above are the known surface from current code reading.)

**Guard helpers used:** `idempotent_create_table`, `idempotent_add_column`, `idempotent_create_foreign_key`, `idempotent_create_unique_constraint`, `idempotent_create_index` — all already shipped in `civiccore.migrations.guards` as part of Phase 1.

---

## 5. Gate-test contract update

ADR-0003 defines three migration gates as required-pass CI checks. Phase 2 extends each:

### Gate 1 — Fresh install (extended)

Asserts that after `alembic upgrade head` on an empty database:
- All 18 expected shared tables exist (was 16: User, Role, Department, audit_log + 12 records-side; now adds `model_registry`, `prompt_templates`).
- `alembic_version_civiccore` carries the latest civiccore revision (`0002`).
- Column shape of `model_registry` matches `civiccore.llm.models.ModelRegistry` (not records-ai's local model — records-ai re-exports from civiccore in v1.4.0).
- Column shape of `prompt_templates` matches the civiccore schema in §6 (override-resolution columns present).

### Gate 2 — Upgrade from prior release (baseline rolls v1.2.0 → v1.3.0)

- Fixture filename changes: `backend/tests/fixtures/schema_v1_2_0.sql` → `backend/tests/fixtures/schema_v1_3_0.sql`. The new fixture is captured from the v1.3.0 release tag using the Step 5a worktree+testcontainer+pg_dump pattern Scott locked at sprint kickoff (Option B; see sprint directive).
- Test renames: `test_gate2_upgrade_from_v1_2` → `test_gate2_upgrade_from_v1_3`.
- Test asserts: starting from a v1.3.0 schema, running `alembic upgrade head` produces a Phase-2 schema with the two new shared tables present, no destructive ALTERs on the records-side `model_registry` / `prompt_templates` rows that existed at v1.3.0, and `alembic_version_civiccore` advances to `0002`.
- The v1.2.0 fixture is retired from CI but kept in the repo under `backend/tests/fixtures/legacy/` for one release cycle, then removed in v1.5.0.

### Gate 3 — civiccore-first install (extended)

Asserts that running `civiccore.migrations.runner.upgrade_to_head()` against an empty database — without records-ai migrations — produces a database containing all 6 civiccore-owned tables (`users`, `roles`, `departments`, `audit_log`, `model_registry`, `prompt_templates`). Then running records-ai's `alembic upgrade head` against that database succeeds with no destructive operations.

---

## 6. Provider abstraction contract

### LLMProvider ABC

Lives at `civiccore.llm.providers.base.LLMProvider`. Required surface:

```python
class LLMProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        *,
        system_prompt: str,
        user_content: str,
        model: str | None = None,
        chunks: list[str] | None = None,
        exemption_rules: list[str] | None = None,
        images: list[str] | None = None,
        timeout: float = 120.0,
    ) -> str: ...

    @abstractmethod
    async def embed(
        self,
        text: str,
        *,
        model: str | None = None,
    ) -> list[float]: ...

    @abstractmethod
    async def embed_batch(
        self,
        texts: list[str],
        *,
        model: str | None = None,
    ) -> list[list[float]]: ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable identifier, e.g. 'ollama', 'openai', 'anthropic'."""

    @property
    @abstractmethod
    def supports_images(self) -> bool: ...
```

Surface is derived from the records-ai status quo: `app/llm/client.py::generate()` (kwargs verbatim) plus `app/ingestion/embedder.py::embed_text()` and `embed_batch()`. No `chat()` method in v0.2.0 — records-ai has no multi-turn chat path today, and adding it speculatively would be scope creep. A future `chat()` method is a v0.3.0 candidate when civicclerk's meeting-summary loop is scoped.

### Registration mechanism: decorator-based registry

`civiccore.llm.providers.registry.PROVIDER_REGISTRY: dict[str, type[LLMProvider]]` plus a `@register_provider("name")` decorator. Consumers and civiccore-internal modules register at import time:

```python
@register_provider("ollama")
class OllamaProvider(LLMProvider): ...
```

**Why decorator over Python entry-points:**
- Records-ai is a single-process FastAPI app; entry-point discovery via `importlib.metadata` adds startup cost and extra wheel-metadata complexity for zero benefit at one-process scale.
- Decorator registration is the simplest pattern that works for both first-party (shipped-with-civiccore) and third-party (consumer-extending-civiccore) providers.
- Discovery is explicit: a consumer adds `import myapp.providers` to its startup and the registration happens.
- An entry-points layer can be added in v0.3.0 if a real third-party plugin ecosystem materializes; until then, YAGNI.

### Per-provider config schema

Pydantic `BaseModel` per provider (e.g., `OllamaConfig`, `OpenAIConfig`, `AnthropicConfig`), each declaring its required fields (`base_url`, `api_key`, `default_model`, etc.). The provider class accepts a config instance in its constructor; `civiccore.llm.factory.build_provider(name: str, config: BaseModel) -> LLMProvider` is the public construction entry point. Pydantic validation catches misconfiguration at startup, not at first generate call.

---

## 7. Prompt-template override resolution

### Schema

`prompt_templates` (civiccore-owned) carries the override-resolution columns:

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` (PK) | unchanged from records-ai's current shape |
| `consumer_app` | `VARCHAR(100)` NOT NULL | new — namespace key, e.g. `"civiccore"`, `"civicrecords-ai"`, `"civicclerk"` |
| `template_name` | `VARCHAR(200)` NOT NULL | renamed from `name`; uniqueness moves to `(consumer_app, template_name, version)` |
| `purpose` | `VARCHAR(50)` | unchanged |
| `system_prompt` | `TEXT` | unchanged |
| `user_prompt_template` | `TEXT` | unchanged |
| `token_budget` | `JSONB` | unchanged |
| `model_id` | `INTEGER` FK → `model_registry.id` | unchanged |
| `version` | `INTEGER` | unchanged |
| `is_active` | `BOOLEAN` | unchanged |
| `is_override` | `BOOLEAN` NOT NULL DEFAULT `false` | new — `true` marks a consumer override; civiccore defaults are `false` |
| `created_by` | `UUID` FK → `users.id` | unchanged |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | unchanged |

Composite unique index: `UNIQUE(consumer_app, template_name, version)`.

### Resolution algorithm (3 steps; first hit wins)

When code calls `civiccore.llm.prompts.get_template(template_name, *, consumer_app)`:

1. **Consumer DB override.** Look up the row matching `consumer_app=<caller's app>`, `template_name=<requested>`, `is_active=true`, highest `version`. If found, return.
2. **Consumer code-level override.** Check the in-memory `OVERRIDE_REGISTRY` populated at module import via `@register_template_override(consumer_app, template_name)`. If found, return.
3. **civiccore default.** Look up the row matching `consumer_app="civiccore"`, `template_name=<requested>`, `is_active=true`, highest `version`. If found, return.

If no step matches: raise `TemplateNotFound(template_name, consumer_app)`. **No silent fallback.** A missing template is a configuration bug, not a runtime degraded mode.

The DB-row override (step 1) takes precedence over the code-level override (step 2) because operators must be able to hot-fix prompts in production without a redeploy. The code-level override exists for tests and for templates the consumer doesn't want stored in a DB row.

---

## 8. Versioning rule

| Package | From | To | Bump | Reason |
|---|---|---|---|---|
| `civiccore` | v0.1.0 | v0.2.0 | minor | New `civiccore.llm` module surface; backward-compatible for v0.1.0 consumers (none of the v0.1.0 surface is removed or signature-changed) |
| `civicrecords-ai` | v1.3.0 | v1.4.0 | minor | New civiccore-v0.2.0 dependency wiring; thin adapter layer in `app.llm` re-exports civiccore's `OllamaProvider`; no records-side public API changes |

The civiccore v0.2.0 wheel becomes the new pinned dependency in `records-ai/backend/pyproject.toml`. The pin is exact (`civiccore==0.2.0`), matching the Phase-1 pin discipline ADR-0003 established.

CHANGELOG entries must land in both projects on the same release day. CivicSuite compatibility matrix updates in the records-ai v1.4.0 release PR per the Phase-1 sequence (CivicSuite tracks `civicrecords-ai 1.4.0 → civiccore 0.2.0`).

---

## 9. Consequences

### Positive

- One LLM provider surface across all CivicSuite products. civicclerk inherits Ollama/OpenAI/Anthropic support for free.
- Prompt templates are operator-tunable in production via the DB override path — no redeploy needed for prompt-only changes.
- The `LLMProvider` ABC makes the local-vs-cloud LLM choice swappable per-deployment (matching the project's "no telemetry, locally-hosted-first" posture).
- The decorator registry keeps consumer-side provider extensions tractable without entry-point machinery.

### Negative

- One more cross-package coupling point. A bug in `civiccore.llm` is a bug in every consumer. Mitigated by: gate tests cover both directions (records-only and civiccore-only), the surface is small (4 ABC methods), and every PR touching `civiccore.llm` is reviewed against the gate-test contract.
- Prompt-template DB rows now carry a `consumer_app` namespace; existing v1.3.0 rows must be backfilled to `consumer_app="civicrecords-ai"` in the records-ai-side data migration that the Step 3 implementer writes. Forgetting this step makes existing prompts unreachable post-upgrade.

### Neutral

- No cost-tracking machinery is added (decision #3). If a future consumer needs spend caps, that's a v0.3.0 decision; it does not block v0.2.0.

---

## 10. Open questions (deferred — not blocking Phase 2)

- **Streaming generate.** Records-ai has no streaming consumer today (`stream: False` is hardcoded in `client.py`). civicclerk may want streaming for live meeting-summary UX. Adding `async def generate_stream(...) -> AsyncIterator[str]` to the ABC is a v0.3.0 candidate, scoped only when civicclerk concretely needs it.
- **Multi-turn chat.** Same shape — defer until a concrete consumer.
- **Cost-tracking and per-tenant caps.** Out of scope for v0.2.0 by decision #3. Re-open only if Scott reverses the decision.
- **Third-party provider plugins via entry-points.** YAGNI until a real third-party provider exists.
