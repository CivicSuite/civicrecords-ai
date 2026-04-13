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
