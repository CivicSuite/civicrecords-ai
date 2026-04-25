"""Tests for central LLM client wiring.

Verifies that llm_reviewer, synthesizer, and llm_extractor all route
through app.llm.client.generate() instead of calling Ollama directly.

Also includes regression tests for the PR #42 audit findings:
- ``_get_provider()`` must construct ``OllamaProvider`` with kwargs (the
  keyword-only signature), not positionally with an ``OllamaConfig``.
- ``generate()`` must call the civiccore provider with
  ``system_prompt`` / ``user_content`` kwargs — NOT the legacy ``prompt=``
  kwarg the records-ai shim used to send.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.llm import client as llm_client_module
from civiccore.llm.providers import OllamaProvider
from civiccore.llm.providers.base import LLMProvider


@pytest.mark.asyncio
async def test_llm_reviewer_uses_central_client():
    """llm_reviewer.llm_suggest_exemptions() routes through app.llm.client.generate()."""
    mock_response = "EXEMPTION|PII|John Doe SSN 123-45-6789|0.9"

    with patch("app.exemptions.llm_reviewer.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_response

        from app.exemptions.llm_reviewer import llm_suggest_exemptions

        result = await llm_suggest_exemptions(
            text="John Doe SSN 123-45-6789 lives at 123 Main St",
            chunk_id=uuid.uuid4(),
            request_id=uuid.uuid4(),
            state_code="CO",
        )

        mock_gen.assert_called_once()
        call_kwargs = mock_gen.call_args.kwargs
        assert "system_prompt" in call_kwargs
        assert "user_content" in call_kwargs
        assert "CO" in call_kwargs["user_content"]

        assert len(result) == 1
        assert result[0]["category"].startswith("LLM:")
        assert result[0]["confidence"] <= 0.7


@pytest.mark.asyncio
async def test_synthesizer_uses_central_client():
    """synthesizer.synthesize_answer() routes through app.llm.client.generate()."""
    from app.search.engine import SearchHit

    mock_answer = "Based on the documents, the city council approved the rezoning. [Doc: minutes.pdf, Page: 3]"

    with patch("app.search.synthesizer.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_answer

        from app.search.synthesizer import synthesize_answer

        hits = [
            SearchHit(
                document_id=uuid.uuid4(),
                chunk_id=uuid.uuid4(),
                filename="minutes.pdf",
                file_type="pdf",
                source_path="/data/minutes.pdf",
                content_text="The council voted 5-2 to approve the rezoning application.",
                similarity_score=0.95,
                page_number=3,
                rank=1,
            ),
        ]

        result = await synthesize_answer(query="Was the rezoning approved?", hits=hits)

        mock_gen.assert_called_once()
        call_kwargs = mock_gen.call_args.kwargs
        assert "system_prompt" in call_kwargs
        assert "Was the rezoning approved?" in call_kwargs["user_content"]
        assert call_kwargs.get("chunks") is not None

        assert "rezoning" in result


@pytest.mark.asyncio
async def test_llm_extractor_uses_central_client():
    """llm_extractor.extract_text_multimodal() routes through app.llm.client.generate()."""
    import tempfile
    from pathlib import Path

    mock_text = "This is extracted text from the scanned document."

    with patch("app.ingestion.llm_extractor.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_text

        from app.ingestion.llm_extractor import extract_text_multimodal

        # Create a minimal test image file (just needs to exist for read_bytes)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)  # Minimal PNG header
            tmp_path = Path(f.name)

        try:
            result = await extract_text_multimodal(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

        mock_gen.assert_called_once()
        call_kwargs = mock_gen.call_args.kwargs
        assert "system_prompt" in call_kwargs
        assert call_kwargs.get("images") is not None
        assert len(call_kwargs["images"]) == 1

        assert result == mock_text


# ---------------------------------------------------------------------------
# Regression tests for PR #42 audit findings
# ---------------------------------------------------------------------------


def test_get_provider_constructs_ollama_provider_with_kwargs(monkeypatch):
    """_get_provider() must construct OllamaProvider with keyword args.

    Regression test: PR #42 originally passed OllamaProvider(OllamaConfig(...))
    positionally, which raises TypeError because OllamaProvider.__init__ is
    keyword-only. This test would have caught that on first run.
    """
    # Reset the module-level provider cache so we exercise the constructor
    monkeypatch.setattr(llm_client_module, "_provider", None)
    provider = llm_client_module._get_provider()
    assert isinstance(provider, OllamaProvider)
    # Provider should be cached on second call
    assert llm_client_module._get_provider() is provider
    # Reset to avoid leaking module state to other tests
    monkeypatch.setattr(llm_client_module, "_provider", None)


class _StrictFakeProvider(LLMProvider):
    """Fake that rejects the legacy 'prompt=' kwarg the records-ai shim used
    to send. Mirrors the civiccore OllamaProvider strictness."""

    def __init__(self) -> None:
        self.last_call_kwargs: dict | None = None

    @property
    def name(self) -> str:
        return "_strict_fake"

    @property
    def supports_images(self) -> bool:
        return True

    async def generate(self, *, system_prompt: str, user_content: str, **kwargs) -> str:
        if "prompt" in kwargs:
            raise TypeError("legacy 'prompt' kwarg not allowed")
        self.last_call_kwargs = {
            "system_prompt": system_prompt,
            "user_content": user_content,
            **kwargs,
        }
        return "FAKE_RESPONSE"

    async def embed(self, text, *, model=None):
        return [0.0]

    async def embed_batch(self, texts, *, model=None):
        return [[0.0] for _ in texts]


def _async_return(value):
    async def _coro(*args, **kwargs):
        return value
    return _coro


@pytest.mark.asyncio
async def test_generate_uses_system_prompt_and_user_content_kwargs(monkeypatch):
    """generate() must call provider with civiccore's signature (system_prompt, user_content).

    Regression: PR #42 originally called provider.generate(prompt=...) which
    raised 'unexpected keyword argument prompt' because civiccore's OllamaProvider
    expects system_prompt + user_content separately.
    """
    fake = _StrictFakeProvider()
    monkeypatch.setattr(llm_client_module, "_provider", fake)

    # Stub out the context-window query so the test doesn't need a DB.
    monkeypatch.setattr(
        llm_client_module,
        "get_active_model_context_window",
        _async_return(8192),
    )

    from app.llm.client import generate

    result = await generate(
        system_prompt="be helpful",
        user_content="hello",
    )
    assert result == "FAKE_RESPONSE"
    assert fake.last_call_kwargs is not None
    assert "prompt" not in fake.last_call_kwargs  # legacy kwarg stripped
    # records-ai inlines the system instruction into the assembled prompt
    # via blocks_to_prompt, then sends it as user_content with system_prompt="".
    assert fake.last_call_kwargs["system_prompt"] == ""
    assert "hello" in fake.last_call_kwargs["user_content"]
