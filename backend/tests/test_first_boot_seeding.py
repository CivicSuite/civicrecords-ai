"""Tests for T5B first-boot seeding (`app.seed.first_boot`).

Proves:
  - A fresh database + admin user produces the full baseline dataset
    (exemption rules + disclosure templates + notification templates).
  - Rerunning the seeder does not duplicate rows.
  - An admin-customized row is preserved on re-seed (skip-if-exists
    upsert policy).
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.exemption import DisclosureTemplate, ExemptionRule
from app.models.notifications import NotificationTemplate
from app.models.user import User, UserRole
from app.seed.first_boot import run_first_boot_seeds


async def _get_admin_user_id(db_session) -> uuid.UUID:
    """Fetch the admin user the conftest fixtures created via admin_token."""
    result = await db_session.execute(
        select(User).where(User.role == UserRole.ADMIN).limit(1)
    )
    admin = result.scalar_one_or_none()
    assert admin is not None, (
        "No admin user found. The admin_token fixture must run before this "
        "test so first-boot seeding has an attribution target."
    )
    return admin.id


@pytest.mark.asyncio
async def test_first_boot_seeds_baseline_dataset(
    client: AsyncClient, admin_token: str, db_session
):
    """Fresh DB + admin → seeder populates the three baseline datasets."""
    admin_id = await _get_admin_user_id(db_session)

    # Baseline counts before seeding (should be zero — client fixture
    # provides a fresh DB).
    pre_rules = (await db_session.execute(select(ExemptionRule))).scalars().all()
    pre_disclosure = (
        await db_session.execute(select(DisclosureTemplate))
    ).scalars().all()
    pre_notif = (
        await db_session.execute(select(NotificationTemplate))
    ).scalars().all()
    assert len(pre_rules) == 0
    assert len(pre_disclosure) == 0
    assert len(pre_notif) == 0

    result = await run_first_boot_seeds(db_session, admin_id)

    # Every dataset reported a non-zero created count.
    assert result["exemption_rules"]["created"] > 0
    assert result["notification_templates"]["created"] > 0
    # disclosure_templates.created may be 0 in a test environment where the
    # markdown source files are not present; `missing_files` records that.
    # But the TOTAL attempted (created + skipped + missing_files) must
    # match the 5 DISCLOSURE_TEMPLATE_FILES entries.
    from scripts.seed_templates import TEMPLATES as DISCLOSURE_TEMPLATE_FILES

    dtot = (
        result["disclosure_templates"]["created"]
        + result["disclosure_templates"]["skipped"]
        + len(result["disclosure_templates"]["missing_files"])
    )
    assert dtot == len(DISCLOSURE_TEMPLATE_FILES), (
        f"Disclosure template accounting mismatch: attempted {dtot} of "
        f"{len(DISCLOSURE_TEMPLATE_FILES)}."
    )

    # Verify DB reflects the seeded baseline.
    rules = (await db_session.execute(select(ExemptionRule))).scalars().all()
    notif = (
        await db_session.execute(select(NotificationTemplate))
    ).scalars().all()

    # State coverage: expect at least one rule for every 50 states + DC.
    state_codes = {r.state_code for r in rules}
    expected_states = {
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
        "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
        "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
        "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
        "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
        "DC",
    }
    assert expected_states.issubset(state_codes), (
        f"Missing state coverage: {expected_states - state_codes}"
    )

    # Universal PII rules are intentionally NOT seeded in T5B because
    # ``ExemptionRule.state_code`` is ``VARCHAR(2)`` and the ``"ALL"``
    # sentinel those rules use cannot fit. Documented in
    # ``app/seed/first_boot.py``; deferred to a follow-on slice that
    # expands the column.
    pii_rules = [r for r in rules if r.state_code == "ALL"]
    assert len(pii_rules) == 0, (
        "Universal PII rules should NOT appear with state_code='ALL' "
        "because the column is VARCHAR(2). If this assertion starts "
        "failing, the schema likely expanded — update the seeder to "
        "include UNIVERSAL_PII_RULES and flip this test accordingly."
    )

    # Notification templates: every event_type from the source list should
    # be represented exactly once.
    from scripts.seed_notification_templates import NOTIFICATION_TEMPLATES

    expected_events = {t["event_type"] for t in NOTIFICATION_TEMPLATES}
    seeded_events = {n.event_type for n in notif}
    assert expected_events.issubset(seeded_events), (
        f"Missing notification event_types: {expected_events - seeded_events}"
    )


@pytest.mark.asyncio
async def test_rerunning_startup_does_not_duplicate(
    client: AsyncClient, admin_token: str, db_session
):
    """Running the seeder twice in a row produces no new rows on the 2nd run.

    Covers the "re-entrant lifespan" contract: Docker restarts, crash
    recovery, or manual ``docker compose up`` reboots must not duplicate
    baseline data.
    """
    admin_id = await _get_admin_user_id(db_session)

    first = await run_first_boot_seeds(db_session, admin_id)
    first_rule_count = len(
        (await db_session.execute(select(ExemptionRule))).scalars().all()
    )
    first_notif_count = len(
        (await db_session.execute(select(NotificationTemplate))).scalars().all()
    )

    second = await run_first_boot_seeds(db_session, admin_id)
    second_rule_count = len(
        (await db_session.execute(select(ExemptionRule))).scalars().all()
    )
    second_notif_count = len(
        (await db_session.execute(select(NotificationTemplate))).scalars().all()
    )

    # Second run created nothing (everything already present).
    assert second["exemption_rules"]["created"] == 0, (
        f"Rerun created {second['exemption_rules']['created']} exemption "
        "rules — not idempotent."
    )
    assert second["notification_templates"]["created"] == 0
    # And the row totals are unchanged.
    assert first_rule_count == second_rule_count, (
        f"Rule row count changed across runs: {first_rule_count} -> "
        f"{second_rule_count}. Seeder is duplicating data."
    )
    assert first_notif_count == second_notif_count, (
        f"Notification row count changed across runs: "
        f"{first_notif_count} -> {second_notif_count}."
    )
    # First-run skipped should be zero (nothing pre-existing);
    # second-run skipped should equal first-run created (every row already
    # there). Pins the skip-if-exists semantics, not just the count.
    assert second["exemption_rules"]["skipped"] == first["exemption_rules"]["created"]
    assert (
        second["notification_templates"]["skipped"]
        == first["notification_templates"]["created"]
    )


@pytest.mark.asyncio
async def test_existing_customized_rows_are_preserved(
    client: AsyncClient, admin_token: str, db_session
):
    """Admin customizations survive a re-seed.

    Scenario: operator seeds baseline, disables a rule, and flips a
    notification template's channel. Lifespan re-runs (Docker restart).
    The customizations must not be reverted — the skip-if-exists policy
    protects them.
    """
    admin_id = await _get_admin_user_id(db_session)

    # Initial seed.
    await run_first_boot_seeds(db_session, admin_id)

    # Customize: disable the first exemption rule, edit the first
    # notification template's channel.
    first_rule = (
        (await db_session.execute(select(ExemptionRule).limit(1))).scalars().first()
    )
    assert first_rule is not None and first_rule.enabled is True
    first_rule.enabled = False
    original_rule_id = first_rule.id
    original_rule_state = first_rule.state_code
    original_rule_category = first_rule.category

    first_notif = (
        (await db_session.execute(select(NotificationTemplate).limit(1)))
        .scalars()
        .first()
    )
    assert first_notif is not None
    original_notif_id = first_notif.id
    original_notif_event = first_notif.event_type
    original_notif_channel = first_notif.channel
    customized_channel = "in_app" if original_notif_channel == "email" else "email"
    first_notif.channel = customized_channel

    await db_session.commit()

    # Re-run the seeder (simulates lifespan restart).
    result = await run_first_boot_seeds(db_session, admin_id)

    # Nothing new created — all rows already present, customizations or not.
    assert result["exemption_rules"]["created"] == 0
    assert result["notification_templates"]["created"] == 0

    # The customizations survived.
    refreshed_rule = (
        await db_session.execute(
            select(ExemptionRule).where(ExemptionRule.id == original_rule_id)
        )
    ).scalar_one()
    assert refreshed_rule.enabled is False, (
        f"Rule {original_rule_state}/{original_rule_category!r} was re-enabled "
        "by the seeder — upsert policy broken, customization reverted."
    )

    refreshed_notif = (
        await db_session.execute(
            select(NotificationTemplate).where(
                NotificationTemplate.id == original_notif_id
            )
        )
    ).scalar_one()
    assert refreshed_notif.channel == customized_channel, (
        f"Notification template {original_notif_event!r} channel was reset "
        f"from {customized_channel!r} back to {original_notif_channel!r} — "
        "upsert policy broken."
    )
