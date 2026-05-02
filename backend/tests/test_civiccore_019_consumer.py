"""CivicCore v0.21.0 shared contract smoke tests for Records-AI."""

from datetime import datetime, timezone

from civiccore.connectors import DELTA_QUERY_PARAMS, plan_vendor_delta_request
from civiccore.testing.mock_city import (
    assert_secret_free_report,
    mock_city_report,
    run_mock_city_backup_retention_suite,
    run_mock_city_contract_suite,
    run_mock_city_idp_contract_suite,
)
from civiccore.security import (
    parse_csv_setting,
    validate_fernet_key_setting,
    validate_password_setting,
    validate_secret_setting,
)
from civiccore.scheduling import compute_next_sync_at, validate_cron_expression


def test_records_ai_can_use_shared_vendor_delta_planner():
    """Records-AI should consume the suite-wide delta URL contract from CivicCore."""

    watermark = datetime(2026, 5, 2, 16, 30, tzinfo=timezone.utc)

    plan = plan_vendor_delta_request(
        connector="legistar",
        source_url="https://legistar.mock-city.example.gov/v1/meetings",
        changed_since=watermark,
    )

    assert DELTA_QUERY_PARAMS["legistar"] == "LastModifiedDate"
    assert plan.connector == "legistar"
    assert plan.cursor_param == "LastModifiedDate"
    assert plan.request_url == (
        "https://legistar.mock-city.example.gov/v1/meetings"
        "?LastModifiedDate=2026-05-02T16%3A30%3A00Z"
    )


def test_records_ai_can_use_shared_mock_city_contract_report():
    """The reusable mock city suite should be usable without CivicClerk imports."""

    report = mock_city_report()

    assert report["mock_city"] == "City of Brookfield"
    assert all(check.ok for check in run_mock_city_contract_suite())
    assert all(check.ok for check in run_mock_city_idp_contract_suite())
    assert all(check.ok for check in run_mock_city_backup_retention_suite())
    assert_secret_free_report(report)


def test_records_ai_consumes_shared_startup_config_validation():
    """Records-AI startup hardening should come from CivicCore, not local copies."""

    assert parse_csv_setting("roles, groups, ,department") == ["roles", "groups", "department"]
    validate_secret_setting("a" * 64, setting_name="JWT_SECRET")
    validate_password_setting("S3cure!FreshAdminPwd-2026", setting_name="FIRST_ADMIN_PASSWORD")

    from cryptography.fernet import Fernet

    validate_fernet_key_setting(Fernet.generate_key().decode(), setting_name="ENCRYPTION_KEY")


def test_records_ai_consumes_shared_schedule_validation():
    """Records-AI scheduler hardening should come from CivicCore, not local copies."""

    validate_cron_expression("*/5 * * * *")
    next_run = compute_next_sync_at("0 2 * * *", None)

    assert next_run.isoformat() == "1970-01-01T02:00:00+00:00"
