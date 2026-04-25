"""Records-ai context-assembly shim — delegates to civiccore.llm.context.

Phase 2 Step 5c: All token budgeting, context-block assembly, and prompt
sanitization logic now lives in :mod:`civiccore.llm.context`. This module
re-exports the public surface so existing records-ai callers
(``app.llm.client``, ingestion, exemptions reviewer, tests) continue to
work without changes.

The one piece of records-ai-specific glue is
:func:`get_active_model_context_window`. Civiccore's signature is
``get_active_model_context_window(session: AsyncSession) -> int`` (caller
supplies the session), but records-ai's historical signature is no-arg —
callers expect this module to open its own session via
:data:`app.database.async_session_maker`. We preserve that contract here.
"""

from __future__ import annotations

import logging

from civiccore.llm.context import (  # noqa: F401
    DEFAULT_CONTEXT_WINDOW,
    ContextBlock,
    TokenBudget,
    assemble_context,
    blocks_to_prompt,
    count_tokens,
    estimate_tokens,
    sanitize_for_llm,
)
from civiccore.llm.registry import (
    get_active_model_context_window as _civiccore_get_active_model_context_window,
)

logger = logging.getLogger(__name__)


async def get_active_model_context_window() -> int:
    """Return the active model's ``context_window_size`` from ``model_registry``.

    Records-ai-flavoured wrapper: opens a session via
    ``app.database.async_session_maker`` and delegates to
    :func:`civiccore.llm.registry.get_active_model_context_window`. Any
    exception (DB unavailable, no active row, etc.) is logged and the
    civiccore default ``DEFAULT_CONTEXT_WINDOW`` is returned so the LLM
    pipeline degrades gracefully rather than failing the request.
    """
    from app.database import async_session_maker

    try:
        async with async_session_maker() as session:
            value = await _civiccore_get_active_model_context_window(session)
            if value and value > 0:
                logger.debug("Active model context window: %d", value)
                return value
    except Exception as exc:  # noqa: BLE001 — best-effort fallback path
        logger.warning(
            "Failed to read model registry, using default context window: %s",
            exc,
        )

    return DEFAULT_CONTEXT_WINDOW


__all__ = [
    "DEFAULT_CONTEXT_WINDOW",
    "ContextBlock",
    "TokenBudget",
    "assemble_context",
    "blocks_to_prompt",
    "count_tokens",
    "estimate_tokens",
    "sanitize_for_llm",
    "get_active_model_context_window",
]
