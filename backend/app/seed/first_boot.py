"""T5B (Tier 5 Blocker B) — first-boot baseline seeding.

Runs automatically from ``app.main`` lifespan after the first admin user
has been created. Populates the three baseline datasets CivicRecords AI
requires for a fresh deployment to be usable:

  1. **Exemption rules** — 175 state-scoped keyword rules across 50 states + DC from
     ``scripts/seed_rules.py::STATE_RULES_REGISTRY``. Seeds the same set
     the existing CLI ``seed()`` entry-point has always seeded; T5B makes
     the seeding automatic instead of requiring a manual post-install step.
     Universal PII regex rules from ``UNIVERSAL_PII_RULES`` are **not**
     seeded here because ``ExemptionRule.state_code`` is ``VARCHAR(2)`` and
     the ``"ALL"`` sentinel those rules use cannot fit. A follow-on slice
     will expand the column (or introduce a nullable semantic) and seed
     universal PII rules then.

  2. **Disclosure templates** — 5 compliance templates (AI use disclosure,
     response letter disclosure, CAIA impact assessment, AI governance
     policy, data residency attestation) from
     ``scripts/seed_templates.py::TEMPLATES``. Content loaded from
     ``backend/compliance_templates/*.md``.

  3. **Notification templates** — 12 event templates from
     ``scripts/seed_notification_templates.py::NOTIFICATION_TEMPLATES``.

**Upsert policy (Scott-approved 2026-04-22):** skip-if-exists on each row's
natural key. Existing customized rows (e.g., an admin who edited a rule's
``enabled`` flag or a template's body text) are **preserved** — the seeder
never overwrites an existing row. Fresh seed data is only written for rows
whose key is not yet present. Re-running the lifespan therefore never
produces duplicates and never reverts operator customizations.

**Logging:** every run emits a start line, per-dataset summary lines with
created/skipped counts, and a completion line, all at INFO level. Callers
that want the structured result also receive a dict.

**Signature:** ``async def run_first_boot_seeds(session, admin_user_id) ->
dict``. Returns::

    {
      "exemption_rules":       {"created": int, "skipped": int},
      "disclosure_templates":  {"created": int, "skipped": int,
                                "missing_files": list[str]},
      "notification_templates":{"created": int, "skipped": int},
    }
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Baseline datasets live in the seed scripts so the CLI and the lifespan
# share a single source of truth. Importing from ``scripts`` works because
# the api image COPYs ``backend/scripts`` to ``/app/scripts`` and ``/app``
# is on the Python path (see Dockerfile.backend).
from scripts.seed_rules import STATE_RULES_REGISTRY
from scripts.seed_templates import TEMPLATE_DIR, TEMPLATES as DISCLOSURE_TEMPLATE_FILES
from scripts.seed_notification_templates import NOTIFICATION_TEMPLATES

from app.models.exemption import DisclosureTemplate, ExemptionRule, RuleType
from app.models.notifications import NotificationTemplate

logger = logging.getLogger(__name__)


async def _seed_exemption_rules(
    session: AsyncSession, admin_user_id: uuid.UUID
) -> dict[str, int]:
    """Seed state-scoped + universal PII exemption rules.

    Natural key: ``(state_code, category)``. Skip if a row with that key
    already exists.
    """
    logger.info("T5B seed: exemption_rules — starting")
    created = 0
    skipped = 0

    for state_code, rules, law_name, state_name in STATE_RULES_REGISTRY:
        for rule_data in rules:
            existing = await session.execute(
                select(ExemptionRule).where(
                    ExemptionRule.category == rule_data["category"],
                    ExemptionRule.state_code == state_code,
                )
            )
            if existing.scalar_one_or_none():
                skipped += 1
                continue
            description = rule_data.get(
                "description",
                f"{state_name} {law_name} exemption: "
                f"{rule_data['category'].replace(f'{law_name} - ', '')}",
            )
            session.add(
                ExemptionRule(
                    state_code=state_code,
                    category=rule_data["category"],
                    rule_type=RuleType.KEYWORD,
                    rule_definition=rule_data["definition"],
                    description=description,
                    enabled=True,
                    created_by=admin_user_id,
                )
            )
            created += 1

    # Universal PII regex rules exist in ``scripts.seed_rules.UNIVERSAL_PII_RULES``
    # but intentionally NOT seeded here — their ``state_code="ALL"`` cannot
    # fit ``ExemptionRule.state_code VARCHAR(2)``. Deferred to a follow-on
    # slice that expands the column (or models universality as nullable).

    await session.commit()
    logger.info(
        "T5B seed: exemption_rules — created=%d skipped=%d",
        created,
        skipped,
    )
    return {"created": created, "skipped": skipped}


async def _seed_disclosure_templates(
    session: AsyncSession, admin_user_id: uuid.UUID
) -> dict[str, int | list[str]]:
    """Seed compliance / disclosure templates.

    Natural key: ``template_type``. Skip if row exists. Missing source
    files are logged at WARNING and reported in ``missing_files``.
    """
    logger.info("T5B seed: disclosure_templates — starting")
    created = 0
    skipped = 0
    missing_files: list[str] = []

    for template_type, filename in DISCLOSURE_TEMPLATE_FILES:
        existing = await session.execute(
            select(DisclosureTemplate).where(
                DisclosureTemplate.template_type == template_type
            )
        )
        if existing.scalar_one_or_none():
            skipped += 1
            continue

        filepath = TEMPLATE_DIR / filename
        if not filepath.exists():
            logger.warning(
                "T5B seed: disclosure_templates — %s source file missing at %s",
                template_type,
                filepath,
            )
            missing_files.append(filename)
            continue

        content = filepath.read_text(encoding="utf-8")
        session.add(
            DisclosureTemplate(
                template_type=template_type,
                content=content,
                updated_by=admin_user_id,
            )
        )
        created += 1

    await session.commit()
    logger.info(
        "T5B seed: disclosure_templates — created=%d skipped=%d missing_files=%d",
        created,
        skipped,
        len(missing_files),
    )
    return {"created": created, "skipped": skipped, "missing_files": missing_files}


async def _seed_notification_templates(
    session: AsyncSession, admin_user_id: uuid.UUID
) -> dict[str, int]:
    """Seed notification event templates.

    Natural key: ``event_type``. Skip if row exists. Note: a single
    ``event_type`` row is kept even if multiple channels exist in the
    source list — this mirrors the existing CLI script's behavior
    (`scripts/seed_notification_templates.py`).
    """
    logger.info("T5B seed: notification_templates — starting")
    created = 0
    skipped = 0

    for tmpl_data in NOTIFICATION_TEMPLATES:
        existing = await session.execute(
            select(NotificationTemplate).where(
                NotificationTemplate.event_type == tmpl_data["event_type"],
            )
        )
        if existing.scalar_one_or_none():
            skipped += 1
            continue
        session.add(
            NotificationTemplate(
                event_type=tmpl_data["event_type"],
                channel=tmpl_data["channel"],
                subject_template=tmpl_data["subject_template"],
                body_template=tmpl_data["body_template"],
                is_active=True,
                created_by=admin_user_id,
            )
        )
        created += 1

    await session.commit()
    logger.info(
        "T5B seed: notification_templates — created=%d skipped=%d",
        created,
        skipped,
    )
    return {"created": created, "skipped": skipped}


async def run_first_boot_seeds(
    session: AsyncSession, admin_user_id: uuid.UUID
) -> dict[str, dict]:
    """Orchestrate all three baseline-seed steps.

    Called from ``app.main.lifespan`` after the first admin user has
    been created and the systems catalog has auto-loaded. Re-entrant:
    every step is skip-if-exists, so repeated startups are safe.
    """
    logger.info("T5B first-boot seeding — starting")
    result = {
        "exemption_rules": await _seed_exemption_rules(session, admin_user_id),
        "disclosure_templates": await _seed_disclosure_templates(
            session, admin_user_id
        ),
        "notification_templates": await _seed_notification_templates(
            session, admin_user_id
        ),
    }
    total_created = sum(v.get("created", 0) for v in result.values())
    total_skipped = sum(v.get("skipped", 0) for v in result.values())
    logger.info(
        "T5B first-boot seeding — complete. total_created=%d total_skipped=%d",
        total_created,
        total_skipped,
    )
    # Print counts as well so operators watching Docker stdout see the
    # outcome even if their LOG_LEVEL filters INFO.
    print(
        f"T5B first-boot seeding: "
        f"exemption_rules={result['exemption_rules']}, "
        f"disclosure_templates={result['disclosure_templates']}, "
        f"notification_templates={result['notification_templates']}"
    )
    return result
