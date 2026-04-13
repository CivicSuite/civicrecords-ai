import re
from pathlib import Path

import pytest
from httpx import AsyncClient

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "compliance_templates"


def test_all_template_files_exist():
    files = [
        "ai-use-disclosure.md",
        "response-letter-disclosure.md",
        "caia-impact-assessment.md",
        "ai-governance-policy.md",
        "data-residency-attestation.md",
    ]
    for f in files:
        path = TEMPLATE_DIR / f
        assert path.exists(), f"Missing template file: {f}"
        content = path.read_text(encoding="utf-8")
        assert len(content) > 100, f"Template {f} is too short"


def test_templates_contain_placeholder_variables():
    for f in TEMPLATE_DIR.glob("*.md"):
        content = f.read_text(encoding="utf-8")
        placeholders = re.findall(r"\{\{(\w+)\}\}", content)
        assert len(placeholders) > 0, f"Template {f.name} has no placeholder variables"
        assert "CITY_NAME" in placeholders, f"Template {f.name} missing {{{{CITY_NAME}}}}"


def test_template_render_replaces_variables():
    template = "Dear {{CITY_NAME}} in {{STATE}}, effective {{EFFECTIVE_DATE}}."
    variables = {"CITY_NAME": "Springfield", "STATE": "Colorado", "EFFECTIVE_DATE": "2026-01-01"}
    rendered = template
    for key, value in variables.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    assert "Springfield" in rendered
    assert "Colorado" in rendered
    assert "2026-01-01" in rendered
    assert "{{" not in rendered


def test_template_render_missing_variables_preserved():
    template = "{{CITY_NAME}} uses {{UNKNOWN_VAR}} system."
    variables = {"CITY_NAME": "Springfield"}
    rendered = template
    for key, value in variables.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    assert "Springfield" in rendered
    assert "{{UNKNOWN_VAR}}" in rendered


@pytest.mark.asyncio
async def test_list_templates_unauthenticated(client: AsyncClient):
    resp = await client.get("/exemptions/templates/")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_template_staff_forbidden(client: AsyncClient, staff_token: str):
    resp = await client.post(
        "/exemptions/templates/",
        json={"template_type": "custom", "content": "test"},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_render_template_with_profile(client: AsyncClient, admin_token: str):
    # Create city profile
    await client.post(
        "/city-profile",
        json={"city_name": "Springfield", "state": "CO"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    # Create a template
    create = await client.post(
        "/exemptions/templates/",
        json={
            "template_type": "test_render",
            "content": "Welcome to {{CITY_NAME}}, {{STATE}}!",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    template_id = create.json()["id"]

    resp = await client.get(
        f"/exemptions/templates/{template_id}/render",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "Springfield" in data["rendered_content"]
    assert "CO" in data["rendered_content"]
    assert data["has_unresolved_variables"] is False


@pytest.mark.asyncio
async def test_render_template_without_profile(client: AsyncClient, admin_token: str):
    create = await client.post(
        "/exemptions/templates/",
        json={
            "template_type": "test_no_profile",
            "content": "Hello {{CITY_NAME}}",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    template_id = create.json()["id"]

    resp = await client.get(
        f"/exemptions/templates/{template_id}/render",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["has_unresolved_variables"] is True


@pytest.mark.asyncio
async def test_update_template_admin(client: AsyncClient, admin_token: str):
    create = await client.post(
        "/exemptions/templates/",
        json={"template_type": "test_update", "content": "Original"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    template_id = create.json()["id"]

    resp = await client.put(
        f"/exemptions/templates/{template_id}",
        json={"content": "Updated content"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == "Updated content"
    assert resp.json()["version"] == 2


@pytest.mark.asyncio
async def test_update_template_staff_forbidden(client: AsyncClient, admin_token: str, staff_token: str):
    create = await client.post(
        "/exemptions/templates/",
        json={"template_type": "test_no_edit", "content": "Original"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    template_id = create.json()["id"]

    resp = await client.put(
        f"/exemptions/templates/{template_id}",
        json={"content": "Hacked"},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert resp.status_code == 403
