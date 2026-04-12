"""Seed exemption rules for Colorado CORA (pilot state)."""
import asyncio
import uuid
from app.database import async_session_maker
from app.models.exemption import ExemptionRule, RuleType
from app.models.user import User
from sqlalchemy import select

COLORADO_CORA_RULES = [
    {"category": "CORA - Trade Secrets", "rule_type": "keyword", "definition": "trade secret,proprietary,confidential business,competitive advantage"},
    {"category": "CORA - Personnel Records", "rule_type": "keyword", "definition": "personnel file,employee evaluation,disciplinary action,performance review,termination"},
    {"category": "CORA - Law Enforcement", "rule_type": "keyword", "definition": "investigation,informant,undercover,surveillance,criminal intelligence"},
    {"category": "CORA - Attorney-Client", "rule_type": "keyword", "definition": "attorney-client,legal privilege,work product,litigation hold,legal opinion"},
    {"category": "CORA - Deliberative Process", "rule_type": "keyword", "definition": "draft recommendation,preliminary analysis,internal deliberation,policy discussion"},
    {"category": "CORA - Medical Records", "rule_type": "keyword", "definition": "medical record,patient,diagnosis,treatment plan,HIPAA,health information"},
    {"category": "CORA - Student Records", "rule_type": "keyword", "definition": "student record,FERPA,academic record,enrollment,grade,transcript"},
    {"category": "CORA - Real Estate Appraisal", "rule_type": "keyword", "definition": "appraisal,property valuation,assessed value,market analysis"},
]


async def seed():
    async with async_session_maker() as session:
        # Get first admin user as creator
        result = await session.execute(select(User).limit(1))
        user = result.scalar_one_or_none()
        if not user:
            print("No users in database. Run the application first.")
            return

        for rule_data in COLORADO_CORA_RULES:
            # Check if rule already exists
            existing = await session.execute(
                select(ExemptionRule).where(
                    ExemptionRule.category == rule_data["category"],
                    ExemptionRule.state_code == "CO",
                )
            )
            if existing.scalar_one_or_none():
                print(f"  Skipped (exists): {rule_data['category']}")
                continue

            rule = ExemptionRule(
                state_code="CO",
                category=rule_data["category"],
                rule_type=RuleType.KEYWORD,
                rule_definition=rule_data["definition"],
                description=f"Colorado CORA exemption: {rule_data['category'].replace('CORA - ', '')}",
                enabled=True,
                created_by=user.id,
            )
            session.add(rule)
            print(f"  Created: {rule_data['category']}")

        await session.commit()
        print(f"\nSeeded {len(COLORADO_CORA_RULES)} Colorado CORA rules.")


if __name__ == "__main__":
    asyncio.run(seed())
