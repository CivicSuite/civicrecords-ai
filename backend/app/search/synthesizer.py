import httpx

from app.config import settings
from app.search.engine import SearchHit

SYNTHESIS_PROMPT = """You are a municipal records assistant helping city staff find responsive documents for open records requests.

Based on the following document excerpts, provide a concise answer to the query. Cite your sources using [Doc: filename, Page: N] format.

IMPORTANT: This is an AI-generated draft requiring human review. Do not make legal determinations.

Query: {query}

Document Excerpts:
{context}

Provide a clear, factual answer based only on the excerpts above. If the excerpts don't contain enough information to answer, say so."""


def _format_context(hits: list[SearchHit]) -> str:
    """Format search hits as context for the LLM prompt."""
    parts = []
    for i, hit in enumerate(hits, 1):
        page_info = f", Page {hit.page_number}" if hit.page_number else ""
        parts.append(f"[{i}] Source: {hit.filename}{page_info}\n{hit.content_text}\n")
    return "\n".join(parts)


async def synthesize_answer(
    query: str,
    hits: list[SearchHit],
    model: str | None = None,
    max_context_hits: int = 5,
) -> str:
    """Generate a synthesized answer from search results using Ollama."""
    model = model or settings.chat_model
    if not hits:
        return "No relevant documents found for this query."

    context = _format_context(hits[:max_context_hits])
    prompt = SYNTHESIS_PROMPT.format(query=query, context=context)

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{settings.ollama_base_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
            },
        )
        if resp.status_code == 200:
            return resp.json().get("response", "Failed to generate answer.")

    return "LLM synthesis unavailable. Review the document excerpts below."
