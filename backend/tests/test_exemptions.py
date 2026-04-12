import uuid
import pytest
from httpx import AsyncClient
from app.exemptions.engine import scan_chunk_builtin, scan_text_with_regex, scan_text_with_keywords


# --- Unit Tests: Rules Engine ---

def test_builtin_pii_detects_ssn():
    flags = scan_chunk_builtin("My SSN is 123-45-6789 and I live in Denver.")
    assert len(flags) >= 1
    assert any(f.category == "PII - SSN" for f in flags)
    assert any("123-45-6789" in f.matched_text for f in flags)


def test_builtin_pii_detects_email():
    flags = scan_chunk_builtin("Contact me at john.doe@example.gov for details.")
    assert len(flags) >= 1
    assert any("Email" in f.category for f in flags)


def test_builtin_pii_detects_phone():
    flags = scan_chunk_builtin("Call us at (303) 555-1234 for more information.")
    assert len(flags) >= 1
    assert any("Phone" in f.category for f in flags)


def test_builtin_pii_no_false_positive():
    flags = scan_chunk_builtin("The city council met on Tuesday to discuss the budget.")
    pii_flags = [f for f in flags if f.category.startswith("PII")]
    assert len(pii_flags) == 0


def test_regex_scanner():
    matches = scan_text_with_regex("SSN: 123-45-6789", r"\d{3}-\d{2}-\d{4}")
    assert len(matches) == 1
    assert matches[0] == "123-45-6789"


def test_keyword_scanner():
    matches = scan_text_with_keywords(
        "This is a trade secret that provides competitive advantage.",
        "trade secret,competitive advantage,proprietary"
    )
    assert len(matches) >= 2


def test_keyword_scanner_case_insensitive():
    matches = scan_text_with_keywords("TRADE SECRET information here.", "trade secret")
    assert len(matches) == 1


def test_keyword_scanner_no_match():
    matches = scan_text_with_keywords("The weather was nice today.", "trade secret,confidential")
    assert len(matches) == 0


# --- API Tests ---

@pytest.mark.asyncio
async def test_create_rule(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/exemptions/rules/",
        json={
            "state_code": "CO",
            "category": "Test Rule",
            "rule_type": "keyword",
            "rule_definition": "test,example",
            "description": "Test exemption rule",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["state_code"] == "CO"
    assert data["category"] == "Test Rule"
    assert data["enabled"] is True


@pytest.mark.asyncio
async def test_create_rule_requires_admin(client: AsyncClient, staff_token: str):
    resp = await client.post(
        "/exemptions/rules/",
        json={"state_code": "CO", "category": "Test", "rule_type": "keyword", "rule_definition": "test"},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_rules(client: AsyncClient, admin_token: str):
    await client.post(
        "/exemptions/rules/",
        json={"state_code": "CO", "category": "List Test", "rule_type": "regex", "rule_definition": "\\d+"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = await client.get("/exemptions/rules/", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_toggle_rule(client: AsyncClient, admin_token: str):
    create = await client.post(
        "/exemptions/rules/",
        json={"state_code": "CO", "category": "Toggle Test", "rule_type": "keyword", "rule_definition": "toggle"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    rule_id = create.json()["id"]

    resp = await client.patch(
        f"/exemptions/rules/{rule_id}",
        json={"enabled": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False


@pytest.mark.asyncio
async def test_dashboard(client: AsyncClient, admin_token: str):
    resp = await client.get("/exemptions/dashboard", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "total_flags" in data
    assert "by_status" in data
    assert "acceptance_rate" in data
    assert "active_rules" in data


@pytest.mark.asyncio
async def test_templates_empty(client: AsyncClient, admin_token: str):
    resp = await client.get("/exemptions/templates/", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_template(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/exemptions/templates/",
        json={"template_type": "ai_disclosure", "state_code": "CO", "content": "This response was prepared with AI assistance."},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["template_type"] == "ai_disclosure"


@pytest.mark.asyncio
async def test_exemptions_require_auth(client: AsyncClient):
    resp = await client.get("/exemptions/rules/")
    assert resp.status_code == 401
