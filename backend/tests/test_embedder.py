import pytest
from unittest.mock import AsyncMock, patch
from app.ingestion.embedder import embed_text, embed_batch, check_model_available

@pytest.mark.asyncio
async def test_embed_text_calls_ollama():
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = lambda: None
    mock_response.json.return_value = {"embeddings": [[0.1, 0.2, 0.3] * 256]}
    with patch("app.ingestion.embedder.httpx.AsyncClient") as mock_client:
        instance = AsyncMock()
        instance.post.return_value = mock_response
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        mock_client.return_value = instance
        result = await embed_text("test text")
        assert len(result) == 768
        instance.post.assert_called_once()

@pytest.mark.asyncio
async def test_embed_batch_calls_ollama():
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = lambda: None
    mock_response.json.return_value = {"embeddings": [[0.1] * 768, [0.2] * 768]}
    with patch("app.ingestion.embedder.httpx.AsyncClient") as mock_client:
        instance = AsyncMock()
        instance.post.return_value = mock_response
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        mock_client.return_value = instance
        result = await embed_batch(["text 1", "text 2"])
        assert len(result) == 2
        assert len(result[0]) == 768

@pytest.mark.asyncio
async def test_embed_batch_empty():
    result = await embed_batch([])
    assert result == []

@pytest.mark.asyncio
async def test_check_model_available():
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"models": [{"name": "nomic-embed-text:latest"}]}
    with patch("app.ingestion.embedder.httpx.AsyncClient") as mock_client:
        instance = AsyncMock()
        instance.get.return_value = mock_response
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        mock_client.return_value = instance
        result = await check_model_available("nomic-embed-text")
        assert result is True
