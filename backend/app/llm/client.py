"""Records-ai LLM generation shim — delegates to civiccore.llm OllamaProvider.

Phase 2 Step 5c: the records-ai-specific ``generate(...)`` entry point is
preserved so existing callers (``app.exemptions.llm_reviewer``,
``app.ingestion.llm_extractor``) keep working unchanged. The body now:

1. Builds context blocks via the records-ai context_manager shim
   (token-budgeted, sanitized) — same pre-flight as before.
2. Delegates the actual HTTP call to a lazily-constructed
   :class:`civiccore.llm.providers.OllamaProvider` bound to records-ai
   settings (``ollama_base_url``, ``chat_model``).

The provider instance is cached at module level. ``OllamaProvider``
lazy-creates its own ``httpx.AsyncClient`` per call internally, so the
records-ai per-call timeout still works via the ``timeout`` kwarg below.
"""

from __future__ import annotations

import logging
from typing import Any

from civiccore.llm.providers import OllamaProvider

from app.config import settings
from app.llm.context_manager import (
    assemble_context,
    blocks_to_prompt,
    get_active_model_context_window,
    sanitize_for_llm,
)

logger = logging.getLogger(__name__)

_OLLAMA_TIMEOUT = 120.0

_provider: OllamaProvider | None = None


def _get_provider() -> OllamaProvider:
    """Lazily construct the module-level OllamaProvider bound to records settings."""
    global _provider
    if _provider is None:
        # OllamaProvider.__init__ is keyword-only — pass kwargs directly,
        # NOT an OllamaConfig positional. OllamaConfig is for build_provider().
        _provider = OllamaProvider(
            base_url=settings.ollama_base_url,
            default_model=settings.chat_model,
        )
    return _provider


async def generate(
    *,
    system_prompt: str,
    user_content: str,
    model: str | None = None,
    chunks: list[str] | None = None,
    exemption_rules: list[str] | None = None,
    images: list[str] | None = None,
    timeout: float = _OLLAMA_TIMEOUT,
) -> str:
    """Generate text via Ollama with context management and sanitization.

    Args:
        system_prompt: The system instruction for the LLM.
        user_content: The primary user/request content (sanitized automatically).
        model: Ollama model name. Defaults to settings.chat_model.
        chunks: Optional document chunks (sanitized via assemble_context).
        exemption_rules: Optional exemption rules (sanitized via assemble_context).
        images: Optional base64-encoded images for multimodal models.
        timeout: Request timeout in seconds.

    Returns:
        The LLM's response text.

    Raises:
        RuntimeError: If the underlying provider call fails.
    """
    resolved_model = model or settings.chat_model

    max_ctx = await get_active_model_context_window()

    blocks = assemble_context(
        system_prompt=system_prompt,
        request_context=sanitize_for_llm(user_content),
        chunks=chunks,
        exemption_rules=exemption_rules,
        max_context_tokens=max_ctx,
    )
    prompt = blocks_to_prompt(blocks)

    extra: dict[str, Any] = {}
    if images:
        extra["images"] = images

    logger.info(
        "LLM generate: model=%s tokens_est=%d chunks=%d rules=%d",
        resolved_model,
        sum(b.estimated_tokens for b in blocks),
        len(chunks or []),
        len(exemption_rules or []),
    )

    provider = _get_provider()
    try:
        # Records-ai already pre-assembled the prompt via assemble_context +
        # blocks_to_prompt above (system instruction inlined at the start of
        # the prompt block). Pass it as user_content with empty system_prompt
        # so civiccore's OllamaProvider routes it to Ollama's `prompt` field
        # without prepending a separate system message. This preserves the
        # records-ai legacy contract: a single text-completion call, not chat.
        result = await provider.generate(
            system_prompt="",
            user_content=prompt,
            model=resolved_model,
            timeout=timeout,
            **extra,
        )
    except Exception as exc:  # noqa: BLE001 — preserve records-ai legacy contract
        logger.error("Ollama generation failed: model=%s err=%s", resolved_model, exc)
        raise RuntimeError(f"Ollama generation failed: {exc}") from exc

    logger.debug("LLM response length: %d chars", len(result))
    return result


__all__ = ["generate"]
