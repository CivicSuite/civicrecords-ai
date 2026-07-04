import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from app.requests.router import (
    _LETTER_DISCLAIMER,
    _parse_ollama_generate_text,
    _try_llm_generation,
    _records_generation_payload,
)


def test_records_generation_payload_uses_pinned_runtime_model(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "civicsuite-gemma4-12b-qat:q4_0")

    payload = _records_generation_payload("Draft a response letter.")

    assert payload["model"] == "civicsuite-gemma4-12b-qat:q4_0"
    assert payload["raw"] is True
    assert payload["stream"] is False
    assert "<start_of_turn>user" in payload["prompt"]
    assert "<start_of_turn>model" in payload["prompt"]
    assert payload["options"]["num_predict"] <= 220
    assert payload["options"]["num_ctx"] <= 3072
    assert "<end_of_turn>" in payload["options"]["stop"]


def test_parse_ollama_generate_text_accepts_response_field():
    body = '{"response":"D105-AI-MODEL-MARKER-20260620 records draft."}'

    assert (
        _parse_ollama_generate_text(body)
        == "D105-AI-MODEL-MARKER-20260620 records draft."
    )


def test_parse_ollama_generate_text_accepts_chat_message_shape():
    body = '{"message":{"content":"D105-AI-MODEL-MARKER-20260620 chat draft."}}'

    assert (
        _parse_ollama_generate_text(body)
        == "D105-AI-MODEL-MARKER-20260620 chat draft."
    )


def test_parse_ollama_generate_text_accepts_chunked_json_lines():
    body = (
        "94\r\n"
        '{"response":"D105-AI-MODEL-"}\n'
        "11\r\n"
        '{"response":"MARKER-20260620 records draft."}\n'
        "0\r\n"
    )

    assert (
        _parse_ollama_generate_text(body)
        == "D105-AI-MODEL-MARKER-20260620 records draft."
    )


@pytest.mark.asyncio
async def test_try_llm_generation_returns_local_ai_letter(monkeypatch):
    captured: dict[str, object] = {}

    class FakeResponse:
        text = '{"response":"D105-AI-MODEL-MARKER-20260620 local records letter."}'

        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        def __init__(self, *, timeout):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, *, json):
            captured["url"] = url
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setenv("LLM_MODEL", "civicsuite-gemma4-12b-qat:q4_0")
    monkeypatch.setattr("app.requests.router.httpx.AsyncClient", FakeAsyncClient)

    req = SimpleNamespace(
        requester_name="D105 Records Requester",
        id=uuid.uuid4(),
        date_received=datetime.now(timezone.utc),
        description="Please provide D105-AI-MODEL-MARKER-20260620 records.",
    )

    generated = await _try_llm_generation(req, [])

    assert generated is not None
    assert "D105-AI-MODEL-MARKER-20260620 local records letter." in generated
    assert _LETTER_DISCLAIMER in generated
    payload = captured["json"]
    assert payload["model"] == "civicsuite-gemma4-12b-qat:q4_0"
    assert payload["raw"] is True
    assert payload["stream"] is False
    assert "D105-AI-MODEL-MARKER-20260620" in payload["prompt"]


@pytest.mark.asyncio
async def test_generate_response_letter(client: AsyncClient, admin_token: str):
    """POST /requests/{id}/response-letter generates a draft letter."""
    create = await client.post(
        "/requests/",
        json={"requester_name": "Letter Test", "description": "Request for budget records"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    req_id = create.json()["id"]
    resp = await client.post(
        f"/requests/{req_id}/response-letter",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["request_id"] == req_id
    assert data["status"] == "draft"
    assert data["generated_content"] is not None
    assert len(data["generated_content"]) > 0
    assert data["id"] is not None


@pytest.mark.asyncio
async def test_get_response_letter(client: AsyncClient, admin_token: str):
    """GET /requests/{id}/response-letter returns the latest letter."""
    create = await client.post(
        "/requests/",
        json={"requester_name": "Get Letter", "description": "Request for permits"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    req_id = create.json()["id"]

    # Generate a letter first
    await client.post(
        f"/requests/{req_id}/response-letter",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # Now retrieve it
    resp = await client.get(
        f"/requests/{req_id}/response-letter",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["request_id"] == req_id
    assert data["status"] == "draft"
    assert "generated_content" in data
