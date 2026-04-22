"""Tests for onboarding LLM-guided interview.

T5A (2026-04-22): the interview endpoint now persists answers in-endpoint
and transitions ``onboarding_status``. The tests below cover:
  - First-time onboarding with no existing CityProfile.
  - Partial-progress persistence across multiple interview round-trips.
  - ``has_dedicated_it`` end-to-end yes/no → bool persistence.
  - ``onboarding_status`` transitions: not_started → in_progress → complete.
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_interview_returns_next_question(client: AsyncClient, admin_token: str):
    """POST /onboarding/interview returns a question and target field."""
    with patch("app.onboarding.router.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = "Welcome! What's the name of your city?"

        resp = await client.post(
            "/onboarding/interview",
            json={},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "question" in data
        assert data["target_field"] is not None
        assert data["all_complete"] is False
        assert isinstance(data["completed_fields"], list)
        # T5A: response now includes onboarding_status.
        assert data["onboarding_status"] == "not_started"


@pytest.mark.asyncio
async def test_interview_skips_completed_fields(client: AsyncClient, admin_token: str):
    """Interview skips fields that already have values in the profile."""
    # Create a city profile with city_name filled
    await client.post(
        "/city-profile",
        json={"city_name": "Springfield", "state": "CO"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    with patch("app.onboarding.router.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = "What county is Springfield in?"

        resp = await client.post(
            "/onboarding/interview",
            json={},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # city_name and state should be in completed_fields
        assert "city_name" in data["completed_fields"]
        assert "state" in data["completed_fields"]
        # target_field should NOT be city_name or state (already filled)
        assert data["target_field"] not in ("city_name", "state")


@pytest.mark.asyncio
async def test_interview_requires_admin(client: AsyncClient):
    """POST /onboarding/interview without admin auth returns 401."""
    resp = await client.post("/onboarding/interview", json={})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_interview_falls_back_on_llm_failure(client: AsyncClient, admin_token: str):
    """Interview returns default question when LLM fails."""
    with patch("app.onboarding.router.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.side_effect = RuntimeError("Ollama unavailable")

        resp = await client.post(
            "/onboarding/interview",
            json={},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Should still return a question (the default fallback)
        assert len(data["question"]) > 0
        assert data["target_field"] is not None


# ─── T5A persistence tests ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_first_time_onboarding_creates_profile(
    client: AsyncClient, admin_token: str
):
    """T5A test 1: first answer to /onboarding/interview creates the CityProfile row.

    Before T5A the interview endpoint was pure-generation and the
    frontend's PATCH /city-profile would 404 silently when no profile
    existed. T5A moves persistence into the interview endpoint itself so
    the first answer creates the row.
    """
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Baseline: no profile yet.
    get_resp = await client.get("/city-profile", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json() is None

    with patch("app.onboarding.router.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = "Which US state is your municipality in?"

        resp = await client.post(
            "/onboarding/interview",
            json={"last_answer": "Denver", "last_field": "city_name"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        # Lifecycle transitioned from not_started to in_progress.
        assert data["onboarding_status"] == "in_progress"
        assert "city_name" in data["completed_fields"]
        assert data["target_field"] != "city_name"

    # Confirm DB persistence via the city-profile read endpoint.
    get_resp = await client.get("/city-profile", headers=headers)
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body is not None
    assert body["city_name"] == "Denver"
    assert body["onboarding_status"] == "in_progress"


@pytest.mark.asyncio
async def test_partial_progress_persists_across_rounds(
    client: AsyncClient, admin_token: str
):
    """T5A test 2: each answer persists and survives across multiple turns."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    with patch("app.onboarding.router.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = "…next question…"

        # Turn 1: city_name.
        r1 = await client.post(
            "/onboarding/interview",
            json={"last_answer": "Lakewood", "last_field": "city_name"},
            headers=headers,
        )
        assert r1.status_code == 200
        assert r1.json()["onboarding_status"] == "in_progress"

        # Turn 2: state.
        r2 = await client.post(
            "/onboarding/interview",
            json={"last_answer": "CO", "last_field": "state"},
            headers=headers,
        )
        assert r2.status_code == 200
        assert r2.json()["onboarding_status"] == "in_progress"

        # Turn 3: county.
        r3 = await client.post(
            "/onboarding/interview",
            json={"last_answer": "Jefferson", "last_field": "county"},
            headers=headers,
        )
        assert r3.status_code == 200
        data3 = r3.json()
        assert data3["onboarding_status"] == "in_progress"
        assert {"city_name", "state", "county"}.issubset(set(data3["completed_fields"]))

    # Verify all three persisted in DB.
    get_resp = await client.get("/city-profile", headers=headers)
    body = get_resp.json()
    assert body["city_name"] == "Lakewood"
    assert body["state"] == "CO"
    assert body["county"] == "Jefferson"
    # Fields not yet answered remain empty.
    assert body["population_band"] is None
    assert body["email_platform"] is None
    assert body["has_dedicated_it"] is None
    assert body["monthly_request_volume"] is None


@pytest.mark.asyncio
async def test_has_dedicated_it_string_to_bool(client: AsyncClient, admin_token: str):
    """T5A test 3: ``has_dedicated_it`` text answer parses to a Python bool.

    Interview collects a natural-language yes/no; CityProfile.has_dedicated_it
    is a Boolean column. The endpoint must normalize or the column explodes.
    """
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Bootstrap with city_name to create the row.
    with patch("app.onboarding.router.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = "…"
        await client.post(
            "/onboarding/interview",
            json={"last_answer": "Boulder", "last_field": "city_name"},
            headers=headers,
        )

        # Answer has_dedicated_it = yes.
        r_yes = await client.post(
            "/onboarding/interview",
            json={"last_answer": "yes", "last_field": "has_dedicated_it"},
            headers=headers,
        )
        assert r_yes.status_code == 200

    body = (await client.get("/city-profile", headers=headers)).json()
    assert body["has_dedicated_it"] is True, (
        f"has_dedicated_it should be True after 'yes' answer, got {body['has_dedicated_it']!r}"
    )

    # Flip to no on the same profile (updating an existing row).
    with patch("app.onboarding.router.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = "…"
        r_no = await client.post(
            "/onboarding/interview",
            json={"last_answer": "no", "last_field": "has_dedicated_it"},
            headers=headers,
        )
        assert r_no.status_code == 200

    body = (await client.get("/city-profile", headers=headers)).json()
    assert body["has_dedicated_it"] is False, (
        f"has_dedicated_it should be False after 'no' answer, got {body['has_dedicated_it']!r}"
    )


@pytest.mark.asyncio
async def test_onboarding_status_transitions(client: AsyncClient, admin_token: str):
    """T5A test 4: onboarding_status transitions not_started → in_progress → complete.

    The 7 tracked fields are: city_name, state, county, population_band,
    email_platform, has_dedicated_it, monthly_request_volume. Answering all
    seven must land the status at ``complete``; anything short is
    ``in_progress``.
    """
    headers = {"Authorization": f"Bearer {admin_token}"}

    # not_started: no profile row exists.
    baseline = await client.post(
        "/onboarding/interview",
        json={},
        headers=headers,
    )
    assert baseline.status_code == 200
    assert baseline.json()["onboarding_status"] == "not_started"

    answers = [
        ("city_name", "Aurora"),
        ("state", "CO"),
        ("county", "Arapahoe"),
        ("population_band", "100,000-500,000"),
        ("email_platform", "Microsoft 365"),
        ("has_dedicated_it", "yes"),
        ("monthly_request_volume", "20-50"),
    ]

    with patch("app.onboarding.router.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = "…next…"

        for i, (field, answer) in enumerate(answers):
            resp = await client.post(
                "/onboarding/interview",
                json={"last_answer": answer, "last_field": field},
                headers=headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            # All turns before the last land in_progress; the final turn
            # completes the walk.
            if i < len(answers) - 1:
                assert data["onboarding_status"] == "in_progress", (
                    f"After turn {i+1} ({field}={answer!r}) status should be in_progress, "
                    f"got {data['onboarding_status']!r}"
                )
            else:
                assert data["onboarding_status"] == "complete", (
                    f"After the final turn status should be complete, "
                    f"got {data['onboarding_status']!r}"
                )
                assert data["all_complete"] is True
                assert data["target_field"] is None

    # Final DB state: every tracked field is populated.
    body = (await client.get("/city-profile", headers=headers)).json()
    assert body["onboarding_status"] == "complete"
    assert body["city_name"] == "Aurora"
    assert body["state"] == "CO"
    assert body["county"] == "Arapahoe"
    assert body["population_band"] == "100,000-500,000"
    assert body["email_platform"] == "Microsoft 365"
    assert body["has_dedicated_it"] is True
    assert body["monthly_request_volume"] == "20-50"


@pytest.mark.asyncio
async def test_skip_advances_past_field_without_persisting(
    client: AsyncClient, admin_token: str
):
    """T5A skip-truth: Skip button must actually advance the walk.

    Pre-fix: skipping a field caused the server to re-ask the same field
    because nothing was persisted and the walk always picked the first
    empty field. The button lied — it claimed to skip while the next
    question was the same question.

    Post-fix: the client supplies `skipped_fields`; the server walks past
    them. DB truth is unchanged — skipped fields stay null and
    onboarding_status stays in_progress until they are answered.
    """
    headers = {"Authorization": f"Bearer {admin_token}"}

    with patch("app.onboarding.router.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = "…"

        # Answer city_name so a profile row exists.
        r1 = await client.post(
            "/onboarding/interview",
            json={"last_answer": "Longmont", "last_field": "city_name"},
            headers=headers,
        )
        assert r1.status_code == 200
        assert r1.json()["target_field"] == "state"

        # Now skip `state`. Server must return `county` as the next field
        # (not `state` again) and must NOT persist state in the DB.
        r2 = await client.post(
            "/onboarding/interview",
            json={
                "last_answer": None,
                "last_field": None,
                "skipped_fields": ["state"],
            },
            headers=headers,
        )
        assert r2.status_code == 200
        data2 = r2.json()
        assert data2["target_field"] == "county", (
            f"Skip must advance past 'state', but server offered "
            f"{data2['target_field']!r} instead."
        )
        assert data2["skipped_fields"] == ["state"]
        assert data2["onboarding_status"] == "in_progress"

    # DB: state remained null; onboarding is not complete.
    body = (await client.get("/city-profile", headers=headers)).json()
    assert body["city_name"] == "Longmont"
    assert body["state"] is None, (
        f"Skipped field 'state' should NOT have persisted a value; "
        f"got {body['state']!r}."
    )
    assert body["onboarding_status"] == "in_progress"


@pytest.mark.asyncio
async def test_skip_closure_when_only_skipped_fields_remain(
    client: AsyncClient, admin_token: str
):
    """T5A skip-truth: when every non-skipped field is populated but some
    are still skipped, the walk ends gracefully with all_complete=False
    and the closure message lists the skipped fields.

    Prevents a regression where the server would return target_field=null
    + all_complete=True even though DB columns were empty.
    """
    headers = {"Authorization": f"Bearer {admin_token}"}

    with patch("app.onboarding.router.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = "…"

        # Fill every field except `county`, carrying county in skipped_fields.
        answers = [
            ("city_name", "Fort Collins"),
            ("state", "CO"),
            ("population_band", "100,000-500,000"),
            ("email_platform", "Google Workspace"),
            ("has_dedicated_it", "yes"),
            ("monthly_request_volume", "5-20"),
        ]
        for field, answer in answers:
            resp = await client.post(
                "/onboarding/interview",
                json={
                    "last_answer": answer,
                    "last_field": field,
                    "skipped_fields": ["county"],
                },
                headers=headers,
            )
            assert resp.status_code == 200

        # After all non-skipped fields: target_field=None, all_complete=False.
        final = await client.post(
            "/onboarding/interview",
            json={"skipped_fields": ["county"]},
            headers=headers,
        )
        assert final.status_code == 200
        data = final.json()
        assert data["target_field"] is None
        assert data["all_complete"] is False
        assert data["onboarding_status"] == "in_progress"
        assert "county" in data["skipped_fields"]
        assert "county" in data["question"], (
            "Closure message must name the skipped field so the operator "
            "knows what's still needed."
        )

    # DB: county stays null.
    body = (await client.get("/city-profile", headers=headers)).json()
    assert body["county"] is None
    assert body["onboarding_status"] == "in_progress"
