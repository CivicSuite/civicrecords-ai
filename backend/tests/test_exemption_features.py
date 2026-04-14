"""Tests for exemption rule history and test modal (Item 1 — Debt Sprint)."""

import pytest
from httpx import AsyncClient


async def _create_rule(client: AsyncClient, token: str, rule_type: str = "keyword", definition: str = "SSN,social security") -> str:
    """Helper to create an exemption rule and return its ID."""
    resp = await client.post(
        "/exemptions/rules/",
        json={
            "state_code": "CO",
            "category": "PII",
            "rule_type": rule_type,
            "rule_definition": definition,
            "description": "Test rule",
            "severity": "high",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_rule_history(client: AsyncClient, admin_token: str):
    """GET /exemptions/rules/{id}/history returns audit entries."""
    rule_id = await _create_rule(client, admin_token)

    resp = await client.get(
        f"/exemptions/rules/{rule_id}/history",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    # Should have at least the create action
    assert len(data) >= 1
    assert data[0]["action"] == "create_exemption_rule"
    assert data[0]["timestamp"] is not None


@pytest.mark.asyncio
async def test_rule_test_keyword_match(client: AsyncClient, admin_token: str):
    """POST /exemptions/rules/{id}/test finds keyword matches."""
    rule_id = await _create_rule(client, admin_token, "keyword", "social security,SSN")

    resp = await client.post(
        f"/exemptions/rules/{rule_id}/test",
        json={"sample_text": "The document contains a social security number SSN 123-45-6789."},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["matched"] is True
    assert len(data["matches"]) >= 2  # "social security" and "SSN"


@pytest.mark.asyncio
async def test_rule_test_no_match(client: AsyncClient, admin_token: str):
    """POST /exemptions/rules/{id}/test returns matched=false when no hits."""
    rule_id = await _create_rule(client, admin_token, "keyword", "classified,top secret")

    resp = await client.post(
        f"/exemptions/rules/{rule_id}/test",
        json={"sample_text": "This is a completely normal public document about park maintenance."},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["matched"] is False
    assert len(data["matches"]) == 0


@pytest.mark.asyncio
async def test_rule_test_regex_match(client: AsyncClient, admin_token: str):
    """POST /exemptions/rules/{id}/test works with regex rules."""
    rule_id = await _create_rule(client, admin_token, "regex", r"\b\d{3}-\d{2}-\d{4}\b")

    resp = await client.post(
        f"/exemptions/rules/{rule_id}/test",
        json={"sample_text": "Found SSN 123-45-6789 in the document."},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["matched"] is True
    assert data["matches"][0]["matched_text"] == "123-45-6789"


@pytest.mark.asyncio
async def test_rule_test_invalid_regex(client: AsyncClient, admin_token: str):
    """POST /exemptions/rules/{id}/test with invalid regex returns 422."""
    rule_id = await _create_rule(client, admin_token, "regex", r"[invalid(")

    resp = await client.post(
        f"/exemptions/rules/{rule_id}/test",
        json={"sample_text": "test text"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422
    assert "Invalid regex" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_rule_test_llm_rule_rejected(client: AsyncClient, admin_token: str):
    """POST /exemptions/rules/{id}/test rejects LLM-type rules."""
    rule_id = await _create_rule(client, admin_token, "llm_prompt", "Check for PII")

    resp = await client.post(
        f"/exemptions/rules/{rule_id}/test",
        json={"sample_text": "test text"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400
    assert "LLM-based rules cannot be tested" in resp.json()["detail"]
