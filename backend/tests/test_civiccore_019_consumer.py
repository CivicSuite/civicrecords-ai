"""CivicCore v0.19.0 shared contract smoke tests for Records-AI."""

from datetime import datetime, timezone

from civiccore.connectors import DELTA_QUERY_PARAMS, plan_vendor_delta_request
from civiccore.testing.mock_city import (
    assert_secret_free_report,
    mock_city_report,
    run_mock_city_backup_retention_suite,
    run_mock_city_contract_suite,
    run_mock_city_idp_contract_suite,
)


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
