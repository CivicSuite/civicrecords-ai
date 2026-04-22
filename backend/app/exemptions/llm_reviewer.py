import logging
import uuid

from app.llm.client import generate

logger = logging.getLogger(__name__)

# T5C: gemma4:e4b is the single truthful default across runtime-config surfaces
# (Tier 5 Blocker 1 resolution 2026-04-21). Caller may override via the model= kwarg.
DEFAULT_MODEL = "gemma4:e4b"

_SYSTEM_PROMPT = """You are reviewing a municipal document excerpt for potential open records exemptions.

For each potential exemption found, respond with ONE LINE per finding in this exact format:
EXEMPTION|category|matched text excerpt|confidence (0.0-1.0)

Common exemption categories: PII, Law enforcement, Legal privilege, Trade secrets, Personnel records, Deliberative process.

If no exemptions are found, respond with:
NONE"""


async def llm_suggest_exemptions(
    text: str,
    chunk_id: uuid.UUID,
    request_id: uuid.UUID,
    state_code: str = "CO",
    model: str = DEFAULT_MODEL,
) -> list[dict]:
    """Use LLM to suggest potential exemptions in text.

    Returns list of dicts with category, matched_text, confidence.
    Lower confidence than rules engine (LLM is secondary).
    Routes through central LLM client for context management and sanitization.
    """
    user_content = f"State: {state_code}\n\nText to review:\n{text[:3000]}"

    try:
        response_text = await generate(
            system_prompt=_SYSTEM_PROMPT,
            user_content=user_content,
            model=model,
        )
    except Exception:
        logger.exception("LLM exemption review failed for chunk %s", chunk_id)
        return []

    if "NONE" in response_text.strip().upper():
        return []

    suggestions = []
    for line in response_text.strip().split("\n"):
        line = line.strip()
        if not line.startswith("EXEMPTION|"):
            continue
        parts = line.split("|")
        if len(parts) >= 4:
            try:
                confidence = min(float(parts[3].strip()) * 0.7, 0.7)  # Cap LLM confidence at 0.7
            except ValueError:
                confidence = 0.5

            suggestions.append({
                "category": f"LLM: {parts[1].strip()}",
                "matched_text": parts[2].strip()[:200],
                "confidence": confidence,
                "chunk_id": chunk_id,
                "request_id": request_id,
            })

    return suggestions
