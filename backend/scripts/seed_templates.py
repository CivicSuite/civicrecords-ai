"""Seed compliance template documents into the disclosure_templates table.

Usage:
    python -m scripts.seed_templates

Idempotent — skips templates that already exist by template_type.
"""
import asyncio
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.exemption import DisclosureTemplate
from app.models.user import User, UserRole

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "compliance_templates"

TEMPLATES = [
    ("ai_use_disclosure", "ai-use-disclosure.md"),
    ("response_letter_disclosure", "response-letter-disclosure.md"),
    ("caia_impact_assessment", "caia-impact-assessment.md"),
    ("ai_governance_policy", "ai-governance-policy.md"),
    ("data_residency_attestation", "data-residency-attestation.md"),
]


async def seed_templates(session: AsyncSession) -> int:
    """Seed compliance templates. Returns count of newly created templates."""
    result = await session.execute(
        select(User).where(User.role == UserRole.ADMIN).limit(1)
    )
    admin = result.scalar_one_or_none()
    if not admin:
        print("ERROR: No admin user found. Create an admin user first.")
        return 0

    created = 0
    for template_type, filename in TEMPLATES:
        existing = await session.execute(
            select(DisclosureTemplate).where(
                DisclosureTemplate.template_type == template_type
            )
        )
        if existing.scalar_one_or_none():
            print(f"  SKIP: {template_type} (already exists)")
            continue

        filepath = TEMPLATE_DIR / filename
        if not filepath.exists():
            print(f"  WARN: {filename} not found at {filepath}")
            continue

        content = filepath.read_text(encoding="utf-8")
        template = DisclosureTemplate(
            template_type=template_type,
            content=content,
            updated_by=admin.id,
        )
        session.add(template)
        created += 1
        print(f"  CREATE: {template_type}")

    await session.commit()
    return created


async def main():
    engine = create_async_engine(settings.database_url)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        count = await seed_templates(session)
        print(f"\nSeeded {count} compliance templates.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
