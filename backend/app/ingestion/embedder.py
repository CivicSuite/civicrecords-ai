"""Records-ai embedding shim — delegates to civiccore.llm OllamaProvider.

Phase 2 Step 5c: replace the records-local httpx calls to ``/api/embed``
with the civiccore-shipped :class:`OllamaProvider`. Public function
signatures are preserved so existing callers (chunker, ingestion pipeline,
search) keep working unchanged.

The provider is constructed lazily at module level and bound to records-ai
settings (``ollama_base_url`` and ``embedding_model`` as the default
``embed`` model).
"""

from __future__ import annotations

import httpx

from civiccore.llm.providers import OllamaProvider

from app.config import settings

_provider: OllamaProvider | None = None


def _get_provider() -> OllamaProvider:
    global _provider
    if _provider is None:
        # OllamaProvider.__init__ is keyword-only; pass the kwargs directly.
        # default_model reuses settings.chat_model so the provider has a
        # sensible default for any non-embed calls; embed/embed_batch below
        # explicitly pass settings.embedding_model so default_model is unused
        # in those paths.
        _provider = OllamaProvider(
            base_url=settings.ollama_base_url,
            default_model=settings.chat_model,
        )
    return _provider


async def embed_text(text: str, model: str | None = None) -> list[float]:
    resolved = model or settings.embedding_model
    provider = _get_provider()
    return await provider.embed(text, model=resolved)


async def embed_batch(texts: list[str], model: str | None = None) -> list[list[float]]:
    resolved = model or settings.embedding_model
    if not texts:
        return []
    provider = _get_provider()
    return await provider.embed_batch(texts, model=resolved)


async def check_model_available(model: str | None = None) -> bool:
    """Probe Ollama's ``/api/tags`` for a given model name.

    Kept as a direct httpx call: civiccore's provider API does not (yet)
    expose a model-listing helper, and this is a simple status probe used
    by the readiness checks. If civiccore later adds ``provider.list_models``
    or similar, swap here.
    """
    resolved = model or settings.embedding_model
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                return any(resolved in m for m in models)
    except Exception:
        pass
    return False
