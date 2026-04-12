import httpx
from app.config import settings

DEFAULT_MODEL = "nomic-embed-text"

async def embed_text(text: str, model: str = DEFAULT_MODEL) -> list[float]:
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{settings.ollama_base_url}/api/embed",
            json={"model": model, "input": text},
        )
        resp.raise_for_status()
        data = resp.json()
        embeddings = data.get("embeddings", [])
        if embeddings and len(embeddings) > 0:
            return embeddings[0]
        raise ValueError(f"No embedding returned from Ollama for model {model}")

async def embed_batch(texts: list[str], model: str = DEFAULT_MODEL) -> list[list[float]]:
    if not texts:
        return []
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{settings.ollama_base_url}/api/embed",
            json={"model": model, "input": texts},
        )
        resp.raise_for_status()
        data = resp.json()
        embeddings = data.get("embeddings", [])
        if len(embeddings) != len(texts):
            raise ValueError(f"Expected {len(texts)} embeddings, got {len(embeddings)}")
        return embeddings

async def check_model_available(model: str = DEFAULT_MODEL) -> bool:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                return any(model in m for m in models)
    except Exception:
        pass
    return False
