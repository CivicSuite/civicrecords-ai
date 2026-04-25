# Phase 2 — civiccore.llm Extraction Scope (records-ai side)

**Status:** SCRATCH — extraction-scope worksheet, not canonical.
**Owners:** records-ai dev (this doc) → civiccore dev (ADR-0004) → implementation.
**Companion:** ADR-0004 (Step 2, civiccore-side) consumes this scope verbatim. Step 3 implementation against `civiccore` main follows it.
**Locked decisions:** Six architecture decisions from the Phase 2 sprint directive are taken as input. They are **not relitigated here**:

1. Prompt templates — civiccore-owned with records-ai override capability. `prompt_templates` table moves to civiccore.
2. Provider clients — pluggable ABC from day one. OpenAI, Anthropic, Ollama as initial implementations.
3. No cost tracking, no budget enforcement. Token-counting utility stays.
4. Shared tables added: `model_registry` + `prompt_templates`. Civiccore total 16 → 18.
5. civiccore version target: v0.2.0.
6. Gate 2 fixture: capture from records-ai v1.3.0 tag using Step 2b worktree + testcontainer + pg_dump pattern.

---

## 1. Modules moving to `civiccore.llm`

Each entry: current records-ai location → proposed civiccore.llm location, what it does, public API surface, deltas required for the move.

### 1.1 Model registry

- **Current location (records-ai):**
  - ORM: `backend/app/models/document.py` lines 149–164 — `class ModelRegistry(Base)` with `__tablename__ = "model_registry"`.
  - Pydantic schemas: `backend/app/schemas/model_registry.py` — `ModelRegistryCreate`, `ModelRegistryRead`, `ModelRegistryUpdate`.
  - HTTP surface: `backend/app/admin/router.py` — admin CRUD endpoints (`/admin/models`, etc.).
  - Migration: `backend/alembic/versions/003_model_registry.py` (initial create) + Phase 2 extension columns added in `787207afc66a_phase2_extensions_12_new_tables_and_.py` (`context_window_size`, `supports_ner`, `supports_vision`).
- **Proposed civiccore location:** `civiccore/llm/registry/` — split into `models.py` (ORM), `schemas.py` (pydantic), `service.py` (CRUD), `router.py` (FastAPI APIRouter mountable by consumers).
- **What it does:** Catalogs available LLMs with provenance metadata (license, model card URL, parameter count) and runtime capability flags (`context_window_size`, `supports_ner`, `supports_vision`). One row per model. Exactly one row may have `is_active=true` — that row drives the runtime context-window budget in `get_active_model_context_window()`.
- **Public API surface (records-ai will import):**
  ```python
  from civiccore.llm.registry import (
      ModelRegistry,                      # SQLAlchemy ORM
      ModelRegistryCreate,                # pydantic
      ModelRegistryRead,                  # pydantic
      ModelRegistryUpdate,                # pydantic
      get_active_model,                   # async helper, returns ModelRegistry row or None
      get_active_model_context_window,    # async helper, returns int (default 8192)
      router as model_registry_router,    # FastAPI APIRouter — mountable
  )
  ```
- **Deltas required for the move:**
  - Move the ORM `Base` reference from `app.models.user.Base` to `civiccore.db.Base` (or whatever civiccore exposes). records-ai must inherit from the same shared `Base` to avoid duplicate-table errors. Spelled out in ADR-0004.
  - Records-ai keeps a thin `app/models/__init__.py` re-export for backwards-compat during the cutover.

### 1.2 Provider abstraction (NEW code, not extracted)

- **Current location (records-ai):** **None.** records-ai today calls Ollama directly via `httpx.AsyncClient` inside `backend/app/llm/client.py::generate()`. There is no provider abstraction, no OpenAI client, no Anthropic client.
- **Proposed civiccore location:** `civiccore/llm/providers/` — `base.py` (ABC), `ollama.py`, `openai.py`, `anthropic.py`, `registry.py` (registration mechanism).
- **What it does:** Defines a uniform `LLMProvider` interface so application code calls `provider.generate(...)` without caring whether the backend is Ollama, OpenAI, or Anthropic. Phase 2 ships three concrete implementations.
- **Public API surface:**
  ```python
  from civiccore.llm.providers import (
      LLMProvider,        # abstract base class
      register_provider,  # decorator OR explicit registration call
      get_provider,       # str -> LLMProvider instance
      list_providers,     # () -> list[str]
  )

  class LLMProvider(ABC):
      name: ClassVar[str]
      @abstractmethod
      async def generate(
          self,
          *,
          system_prompt: str,
          user_content: str,
          model: str,
          images: list[str] | None = None,
          timeout: float = 120.0,
      ) -> str: ...

      @abstractmethod
      def count_tokens(self, text: str, model: str) -> int: ...
  ```
- **Registration mechanism choice — registry decorator (NOT setuptools entry-points):**
  - **Picked:** in-process registry with a `@register_provider` decorator that writes to a module-level dict.
  - **Why not entry-points:** entry-points are a packaging-time discovery mechanism. They require every consumer to install the provider package separately, add a setuptools/pyproject `[project.entry-points]` declaration, and re-install on change. For a 3-provider built-in set that ships inside civiccore itself, this is overhead with no payoff. Entry-points become valuable when third parties ship providers out-of-tree; civiccore can add entry-point discovery as a later additive layer without breaking the registry API.
  - **Why decorator over `register_provider("name", cls)` calls:** decorators co-locate the registration with the class definition. There is exactly one place in code where each provider is wired in.
  - **Initialization:** `civiccore.llm.providers.__init__.py` imports `ollama`, `openai`, `anthropic` so the decorators fire at import time.
  - **Conflict policy:** `register_provider` raises if a name is already taken. No silent override.
- **Deltas:** records-ai's existing direct Ollama call in `backend/app/llm/client.py::generate()` is rewritten to delegate to `civiccore.llm.providers.get_provider("ollama").generate(...)`. Behavior preserved; transport changed.

### 1.3 Prompt template engine

- **Current location (records-ai):**
  - ORM: `backend/app/models/prompts.py` — `class PromptTemplate(Base)` with `__tablename__ = "prompt_templates"`. Columns: `id`, `name` (unique), `purpose`, `system_prompt`, `user_prompt_template`, `token_budget` (JSONB), `model_id` (FK → model_registry), `version`, `is_active`, `created_by`, `created_at`.
  - Migration: `backend/alembic/versions/787207afc66a_phase2_extensions_12_new_tables_and_.py` (Phase 2 extension migration that created prompt_templates alongside 11 other tables).
  - Rendering: **No central rendering engine exists today.** The `user_prompt_template` column is stored as Text; current callers (`exemptions/llm_reviewer.py`, `ingestion/llm_extractor.py`) construct prompts via Python f-strings inline. Phase 2 will introduce the rendering engine fresh.
- **Proposed civiccore location:** `civiccore/llm/templates/` — `models.py` (ORM with override-resolution columns), `schemas.py`, `engine.py` (rendering), `resolver.py` (override-resolution algorithm).
- **What it does:** Stores reusable prompt scaffolding (system + user template) keyed by name. Renders the user template against a context dict. Resolves the right template for a given consumer app, honoring records-ai (and future civicclerk) overrides over civiccore defaults.
- **Template engine choice — `string.Template` (PEP 292), NOT Jinja2 or `str.format`:**
  - **Picked:** `string.Template` from Python stdlib with `safe_substitute()`.
  - **Why not Jinja2:** Jinja2 brings ~250KB of dependencies, autoescape semantics tuned for HTML, and a full DSL (loops, conditionals, filters) we don't need. Existing call sites use plain variable interpolation only. Adding Jinja2 widens the supply-chain surface for no current capability gain.
  - **Why not `str.format` / f-string-style braces:** `{...}` collides with literal JSON braces in many real-world prompts (the LLM is often shown JSON examples). `string.Template` uses `$name` / `${name}` which essentially never collides with prompt content.
  - **Why not Mako/Chevron/Mustache:** same dependency-cost objection, plus stdlib `string.Template` covers 100% of current usage.
  - **Upgrade path:** if a future template legitimately needs loops or conditionals, `string.Template` is the wrong tool — at that point we revisit. Adding Jinja2 later without a real need would be premature.
- **Public API surface:**
  ```python
  from civiccore.llm.templates import (
      PromptTemplate,       # SQLAlchemy ORM
      PromptTemplateCreate, # pydantic
      PromptTemplateRead,   # pydantic
      resolve_template,     # async, override-aware lookup
      render_template,      # PromptTemplate, dict[str, str] -> rendered str
      TemplateNotFound,     # raised when no template matches
  )
  ```
- **Deltas:** PromptTemplate gains override-resolution columns (see §4.2). The Phase 2 extension migration's `prompt_templates` create remains in records-ai history (idempotent guard makes it a no-op once civiccore owns the table) — ADR-0004 will specify the cutover.

### 1.4 Structured-output handling

- **Current location (records-ai):** **None as a generic helper.** `exemptions/llm_reviewer.py::llm_suggest_exemptions` does ad-hoc line-parsing of pipe-delimited LLM output (`EXEMPTION|category|text|confidence`), with no schema validation and no retry. No Pydantic-validated LLM-output pattern exists today.
- **Proposed civiccore location:** `civiccore/llm/structured.py`.
- **What it does:** Wraps a provider call with: (a) inject schema description into the system prompt, (b) attempt `provider.generate()`, (c) parse JSON, (d) validate against a Pydantic model, (e) on failure, retry up to 3 times with the validation error fed back to the model as additional context. Returns the validated model instance or raises `StructuredOutputFailure` after exhausting retries.
- **Public API surface:**
  ```python
  from civiccore.llm.structured import (
      StructuredOutput,         # generic helper class, parameterized by pydantic model
      StructuredOutputFailure,  # raised after retries exhausted
  )

  result: MyPydanticModel = await StructuredOutput(MyPydanticModel).generate(
      provider=get_provider("ollama"),
      system_prompt=...,
      user_content=...,
      model="gemma4:e4b",
      max_attempts=3,
  )
  ```
- **Deltas:** This is **net-new code in civiccore**. records-ai's existing `llm_reviewer.py` line-parsing stays put for now (FOIA-specific format) and is not blocked by this work. Future records-ai code that wants validated JSON output uses the helper.

### 1.5 Token counting utility

- **Current location (records-ai):** `backend/app/llm/context_manager.py::estimate_tokens()` (chars/4 heuristic) and the entire `assemble_context` / `blocks_to_prompt` machinery + `TokenBudget` dataclass + `sanitize_for_llm` prompt-injection defense.
- **Proposed civiccore location:** `civiccore/llm/context.py` (or split into `civiccore/llm/{tokens,context,sanitize}.py` if size warrants — ADR-0004 picks the file layout).
- **What it does:**
  - `estimate_tokens(text)` — fast chars/4 heuristic. Used everywhere context manager runs.
  - `count_tokens(text, model)` — provider-aware. Default impl delegates to `estimate_tokens`. Phase 2 OpenAI/Anthropic providers can override to use `tiktoken` for accurate counts; Ollama provider keeps the heuristic.
  - `assemble_context(...)` — token-budgeted prompt assembly.
  - `sanitize_for_llm(text)` — prompt-injection defense (role-override patterns, delimiter injection, repetition collapse).
- **Public API:**
  ```python
  from civiccore.llm.context import (
      TokenBudget, ContextBlock,
      estimate_tokens, count_tokens,
      assemble_context, blocks_to_prompt,
      sanitize_for_llm,
      get_active_model_context_window,  # also re-exported from registry
  )
  ```
- **Deltas:** `get_active_model_context_window()` currently lives in `app/llm/context_manager.py` but queries `ModelRegistry`. After the move, it lives near the registry (`civiccore.llm.registry.service`) and is re-exported from `civiccore.llm.context` for ergonomics. Per locked decision #3: token counting stays as a utility; **no cost calculation, no budget enforcement** is introduced.

---

## 2. Modules staying in records-ai

Each entry: current location, why it stays.

### 2.1 Disclosure-letter / response-letter generation

- **Location:** records-ai response-generation pipeline (currently distributed across the request-workflow code; no single dedicated module yet).
- **Why it stays:** The output format (disclosure letter, denial letter, partial-grant letter) is FOIA-specific and varies by jurisdiction (state code). It composes civiccore prompt templates + civiccore providers + civiccore structured-output helpers, but the orchestration is a records-ai application concern.

### 2.2 Document classification rules (FOIA semantics)

- **Location:** records-ai exemption rules engine + `exemptions/router.py` plumbing.
- **Why it stays:** Categories (PII, Law enforcement, Legal privilege, Trade secrets, Personnel records, Deliberative process) are FOIA-domain vocabulary. Civiccore should not know what an "exemption" is.

### 2.3 LLM exemption reviewer (`backend/app/exemptions/llm_reviewer.py`)

- **Why it stays:** Wraps a civiccore LLM call with FOIA-specific system prompt, FOIA-specific output parsing (`EXEMPTION|category|text|confidence`), confidence-cap policy (LLM cap at 0.7 because it's secondary to rules), and persists results into `exemption_suggestions`. All of that is records-application logic.
- **Post-Phase-2 shape:** `from civiccore.llm.providers import get_provider` replaces today's `from app.llm.client import generate`. The records-side prompt + parser stays in records-ai.

### 2.4 LLM multimodal extractor (`backend/app/ingestion/llm_extractor.py`)

- **Why it stays:** Multimodal OCR for scanned-PDF ingestion is a records-ai pipeline stage. The `_OCR_SYSTEM_PROMPT` is fine to civiccore-template-ize later if a second consumer needs it, but for v0.2.0 the cost of moving it without a second caller is higher than the cost of leaving it.
- **Post-Phase-2 shape:** Same delegation pattern — call `civiccore.llm.providers.get_provider(...).generate(images=[...])`.

### 2.5 Anything in the request lifecycle that USES LLM as a tool

- Request triage, scope assessment, clarification drafting — all invoke LLM via civiccore but live as records-ai workflow code.

---

## 3. Public API surface — full import list

What records-ai (and eventually civicclerk) imports from civiccore after Phase 2:

```python
from civiccore.llm import (
    # Providers
    LLMProvider,
    register_provider,
    get_provider,
    list_providers,

    # Templates
    PromptTemplate,
    PromptTemplateCreate, PromptTemplateRead,
    resolve_template,
    render_template,
    TemplateNotFound,

    # Registry
    ModelRegistry,
    ModelRegistryCreate, ModelRegistryRead, ModelRegistryUpdate,
    get_active_model,
    get_active_model_context_window,
    model_registry_router,

    # Context / tokens / sanitize
    TokenBudget, ContextBlock,
    estimate_tokens, count_tokens,
    assemble_context, blocks_to_prompt,
    sanitize_for_llm,

    # Structured output
    StructuredOutput,
    StructuredOutputFailure,
)
```

### 3.1 Override-resolution algorithm (formal, 3 steps)

When records-ai code calls `resolve_template(template_name, *, consumer_app="civicrecords-ai")`:

1. **Caller invokes** `resolve_template(template_name, consumer_app=...)`. The `consumer_app` arg defaults to whatever the caller's package is (records-ai sets it to `"civicrecords-ai"` at the call site or via a shared constant). `template_name` is the logical name (e.g., `"exemption_review.system"`).

2. **Lookup order** (first hit wins, no silent fallback):
   - **(a) records-ai instance overrides** — DB row in `prompt_templates` where `name = template_name` AND `consumer_app = "civicrecords-ai"` AND `is_active = true`. These are operator-customized prompts created via the records-ai admin UI.
   - **(b) records-ai code-level overrides** — Python-registered overrides via `civiccore.llm.templates.register_code_override("civicrecords-ai", template_name, PromptTemplate(...))`. These are records-ai shipped defaults that supersede civiccore's, baked into the records-ai codebase.
   - **(c) civiccore defaults** — DB row where `name = template_name` AND (`consumer_app = "civiccore"` OR `consumer_app IS NULL`) AND `is_active = true`. These are civiccore's shipped defaults.

3. **No silent fallback.** If none of (a), (b), (c) match, raise `TemplateNotFound(template_name, consumer_app)` with both fields in the exception message. **Never** return a stub default, never substitute an empty prompt, never log-and-continue. A missing template is a configuration error and must surface immediately.

---

## 4. Shared table list

Civiccore total goes from 16 → 18. The two added tables:

### 4.1 `model_registry` (existing in civiccore-records-bridge — confirm in ADR-0004 whether it's already there)

| column | type | nullable | default | notes |
| --- | --- | --- | --- | --- |
| `id` | INTEGER | NO | autoincrement | PK |
| `model_name` | VARCHAR(255) | NO | — | e.g. `"gemma4:e4b"` |
| `model_version` | VARCHAR(100) | YES | NULL | |
| `parameter_count` | VARCHAR(50) | YES | NULL | e.g. `"4B"` |
| `license` | VARCHAR(100) | YES | NULL | e.g. `"Gemma Terms"` — compliance metadata |
| `model_card_url` | TEXT | YES | NULL | |
| `is_active` | BOOLEAN | NO | `false` | exactly one row should be `true` at runtime |
| `added_at` | TIMESTAMPTZ | YES | `now()` | |
| `context_window_size` | INTEGER | YES | NULL | drives budget scaling in `assemble_context` |
| `supports_ner` | BOOLEAN | NO | `false` | |
| `supports_vision` | BOOLEAN | NO | `false` | OCR / multimodal capability flag |

- **Indexes:** PK on `id`. No others required (single-row active lookup is cheap).
- **FK constraints:** none outbound. Inbound: `prompt_templates.model_id` → `model_registry.id` (ON DELETE SET NULL).
- **Records-ai migrations historically touching this table:**
  - `003_model_registry.py` — initial create.
  - `787207afc66a_phase2_extensions_12_new_tables_and_.py` — added `context_window_size`, `supports_ner`, `supports_vision`.
  - `011_fix_schema_drift.py` — review during ADR-0004 (may have touched ModelRegistry as part of drift fix).
- **Idempotency for ADR-0004:** civiccore must wrap its own `model_registry` create in `idempotent_create_table(...)` (already used by records-ai migration 003). Records-ai's 003 stays in history; on a fresh civicrecords-ai install where civiccore creates the table first, 003 becomes a no-op. ADR-0004 specifies the column-add idempotency for the Phase 2 extension columns.

### 4.2 `prompt_templates` (currently records-ai-owned, moves to civiccore)

| column | type | nullable | default | notes |
| --- | --- | --- | --- | --- |
| `id` | UUID | NO | `uuid4()` | PK |
| `name` | VARCHAR(200) | NO | — | logical name; **was `unique` in records-ai — drop the unique constraint** because override rows share the name with the default |
| `consumer_app` | VARCHAR(100) | NO | `'civiccore'` | **NEW — override-resolution column.** Values: `'civiccore'`, `'civicrecords-ai'`, `'civicclerk'`, etc. |
| `is_override` | BOOLEAN | NO | `false` | **NEW — convenience flag.** True when `consumer_app != 'civiccore'`. Redundant with `consumer_app != 'civiccore'` but cheap to filter by. |
| `parent_template_id` | UUID | YES | NULL | **NEW — optional FK to the civiccore default this overrides.** ON DELETE SET NULL. Used for "diff against default" tooling later; not used by `resolve_template` itself (resolver uses `name + consumer_app` only). |
| `purpose` | VARCHAR(50) | NO | — | e.g. `"exemption_scan"`, `"response_generation"` |
| `system_prompt` | TEXT | NO | — | |
| `user_prompt_template` | TEXT | NO | — | `string.Template` syntax (`$var`) |
| `token_budget` | JSONB | YES | `{}` | optional `TokenBudget` overrides |
| `model_id` | INTEGER | YES | NULL | FK → `model_registry(id)` ON DELETE SET NULL |
| `version` | INTEGER | NO | `1` | bumped on edit; old versions retained for audit |
| `is_active` | BOOLEAN | NO | `true` | only `is_active=true` rows are eligible for resolution |
| `created_by` | UUID | YES | NULL | FK → `users(id)` ON DELETE SET NULL |
| `created_at` | TIMESTAMPTZ | NO | `now()` | |

- **Indexes:**
  - `(name, consumer_app, is_active)` — composite covering the resolver's hot lookup. Unique partial index where `is_active=true` to prevent two active rows for the same `(name, consumer_app)` pair.
  - `(consumer_app)` — supports admin UI filter.
- **FK constraints:**
  - `model_id` → `model_registry(id)` ON DELETE SET NULL.
  - `created_by` → `users(id)` ON DELETE SET NULL.
  - `parent_template_id` → `prompt_templates(id)` ON DELETE SET NULL.
- **Records-ai migrations historically touching this table:**
  - `787207afc66a_phase2_extensions_12_new_tables_and_.py` — initial create (Phase 2 extension batch that added 12 tables in one revision).
- **Idempotency for ADR-0004:** civiccore creates `prompt_templates` via `idempotent_create_table`. The records-ai 787207afc66a migration must be patched (or guarded) so its `prompt_templates` create becomes a no-op when civiccore has created it first. ADR-0004 specifies the patch surgery — likely either (a) split the existing batch migration to gate the prompt_templates create behind an existence check, or (b) add a follow-up migration that drops + civiccore-recreates with the new override columns. Decision deferred to Step 2.

---

## Open questions for Step 2 (ADR-0004)

These are NOT decisions to make in this scope doc — they are flags for the ADR author:

1. **records-ai migration 787207afc66a surgery** — patch in place vs. follow-up migration vs. data-preserving recreate.
2. **`Base` reuse** — single SQLAlchemy declarative base shared across civiccore and records-ai vs. separate bases with cross-table FKs (the FK approach has known Alembic autogenerate quirks).
3. **`model_registry` initial-seed ownership** — does civiccore ship a default `gemma4:e4b` row, or does records-ai keep seeding it via `app/seed/first_boot.py`?
4. **Provider package extras** — `civiccore[openai]`, `civiccore[anthropic]`, `civiccore[ollama]` as optional installs vs. all-three-required. Probably extras, since records-ai today only needs Ollama in production.
5. **Consumer-app constant** — does civiccore export `CONSUMER_APP_CIVICRECORDS = "civicrecords-ai"` for callers, or is the string baked at every call site?

---

## Out of scope (Phase 2 explicitly does NOT do)

- Cost tracking. Per locked decision #3.
- Budget enforcement / quota system. Per locked decision #3.
- Cache layer for LLM responses (separate concern, would live in `civiccore.llm.cache` if added later).
- Streaming token responses (Phase 2 stays request/response).
- Tool-use / function-calling abstraction (deferred to Phase 3 if/when records-ai needs it).
- Civicclerk integration (civicclerk doesn't exist yet; designing for it is YAGNI — but the API shape above does not block its later arrival).
