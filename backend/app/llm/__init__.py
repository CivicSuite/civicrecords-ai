"""Records-ai LLM integration shim — re-exports civiccore.llm public API.

Phase 2 Step 5c: records-ai no longer maintains its own LLM stack. All
provider, template, registry, and context-assembly logic lives in
``civiccore.llm`` (>=0.2.0). This module re-exports the symbols that
records-ai application code historically imported from ``app.llm`` so
existing call sites continue to work unchanged.

The thin wrappers in :mod:`app.llm.client` and :mod:`app.llm.context_manager`
provide the small amount of records-ai-specific glue (lazy provider
construction bound to records-ai settings, and a no-arg
``get_active_model_context_window`` that opens its own session via
records-ai's ``async_session_maker``).
"""

from civiccore.llm import (  # noqa: F401
    # Providers
    LLMProvider,
    OllamaProvider,
    OllamaConfig,
    OpenAIProvider,
    OpenAIConfig,
    AnthropicProvider,
    AnthropicConfig,
    register_provider,
    get_provider,
    list_providers,
    PROVIDER_REGISTRY,
    build_provider,
    CONFIG_SCHEMAS,
    # Templates
    PromptTemplate,
    PromptTemplateCreate,
    PromptTemplateRead,
    RenderedPrompt,
    render_template,
    resolve_template,
    CIVICCORE_DEFAULT_APP,
    PromptTemplateError,
    PromptTemplateNotFoundError,
    PromptTemplateRenderError,
    OVERRIDE_REGISTRY,
    register_template_override,
    unregister_template_override,
    # Registry
    ModelRegistry,
    ModelRegistryCreate,
    ModelRegistryRead,
    ModelRegistryUpdate,
    model_registry_router,
    MissingModelError,
    ModelRegistryServiceError,
    get_active_model,
    require_active_model,
    # Context utilities
    TokenBudget,
    ContextBlock,
    estimate_tokens,
    count_tokens,
    sanitize_for_llm,
    assemble_context,
    blocks_to_prompt,
    DEFAULT_CONTEXT_WINDOW,
    # Structured output
    StructuredOutput,
    StructuredOutputFailure,
    DEFAULT_MAX_ATTEMPTS,
)

# Records-ai-specific glue surfaces.
from app.llm.context_manager import get_active_model_context_window  # noqa: F401,E402
from app.llm.client import generate  # noqa: F401,E402

__all__ = [
    # Providers
    "LLMProvider",
    "OllamaProvider",
    "OllamaConfig",
    "OpenAIProvider",
    "OpenAIConfig",
    "AnthropicProvider",
    "AnthropicConfig",
    "register_provider",
    "get_provider",
    "list_providers",
    "PROVIDER_REGISTRY",
    "build_provider",
    "CONFIG_SCHEMAS",
    # Templates
    "PromptTemplate",
    "PromptTemplateCreate",
    "PromptTemplateRead",
    "RenderedPrompt",
    "render_template",
    "resolve_template",
    "CIVICCORE_DEFAULT_APP",
    "PromptTemplateError",
    "PromptTemplateNotFoundError",
    "PromptTemplateRenderError",
    "OVERRIDE_REGISTRY",
    "register_template_override",
    "unregister_template_override",
    # Registry
    "ModelRegistry",
    "ModelRegistryCreate",
    "ModelRegistryRead",
    "ModelRegistryUpdate",
    "model_registry_router",
    "MissingModelError",
    "ModelRegistryServiceError",
    "get_active_model",
    "require_active_model",
    "get_active_model_context_window",
    # Context utilities
    "TokenBudget",
    "ContextBlock",
    "estimate_tokens",
    "count_tokens",
    "sanitize_for_llm",
    "assemble_context",
    "blocks_to_prompt",
    "DEFAULT_CONTEXT_WINDOW",
    # Structured output
    "StructuredOutput",
    "StructuredOutputFailure",
    "DEFAULT_MAX_ATTEMPTS",
    # Records-ai-local
    "generate",
]
