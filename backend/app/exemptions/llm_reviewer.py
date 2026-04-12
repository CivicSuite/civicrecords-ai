import uuid

import httpx

from app.config import settings
from app.models.exemption import ExemptionFlag, FlagStatus

DEFAULT_MODEL = "gemma4:26b"

LLM_EXEMPTION_PROMPT = """You are reviewing a municipal document excerpt for potential open records exemptions.

State: {state_code}

Review this text and identify any content that might be exempt from public disclosure. Common exemption categories include:
- Personal Identifiable Information (PII): SSNs, addresses, phone numbers, medical info
- Law enforcement: ongoing investigations, informant identities, security procedures
- Legal privilege: attorney-client communications, work product
- Trade secrets: proprietary business information
- Personnel records: employee evaluations, disciplinary actions
- Deliberative process: internal policy discussions, draft recommendations

For each potential exemption found, respond with ONE LINE per finding in this exact format:
EXEMPTION|category|matched text excerpt|confidence (0.0-1.0)

If no exemptions are found, respond with:
NONE

Text to review:
{text}"""


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
    """
    prompt = LLM_EXEMPTION_PROMPT.format(state_code=state_code, text=text[:3000])

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{settings.ollama_base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
            )
            if resp.status_code != 200:
                return []

            response_text = resp.json().get("response", "")
    except Exception:
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
