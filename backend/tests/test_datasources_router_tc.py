"""
Unit tests for test-connection endpoint safety:
- Credential scrubbing
- Recursive JSONB credential walk (no flat .get() allowed)
"""
import pytest
from app.datasources.router import _scrub_error


CREDENTIAL_FIELDS = {"api_key", "token", "client_secret", "password", "connection_string"}


def _find_credentials_recursive(obj, path="root"):
    """
    Recursively walk a JSON-like object and return all paths where
    a credential field name appears as a dict key.
    """
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in CREDENTIAL_FIELDS:
                found.append(f"{path}.{k}")
            found.extend(_find_credentials_recursive(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            found.extend(_find_credentials_recursive(item, f"{path}[{i}]"))
    return found


def test_scrub_error_removes_api_key():
    msg = "Failed: api_key=secretvalue123"
    scrubbed = _scrub_error(msg)
    assert "secretvalue123" not in scrubbed
    assert "api_key" in scrubbed


def test_scrub_error_removes_password():
    msg = "connection_string=DSN=prod;Password=hunter2;UID=admin"
    scrubbed = _scrub_error(msg)
    assert "hunter2" not in scrubbed


def test_recursive_walk_flat():
    response = {"success": True, "latency_ms": 42, "status": "healthy"}
    found = _find_credentials_recursive(response)
    assert found == [], f"Credential fields found in response: {found}"


def test_recursive_walk_nested():
    """Simulate a response that accidentally nested a config object."""
    response = {
        "success": True,
        "details": {
            "connector": {
                "api_key": "leaked!",
                "base_url": "https://example.gov",
            }
        }
    }
    found = _find_credentials_recursive(response)
    assert "root.details.connector.api_key" in found


def test_recursive_walk_in_list():
    response = {
        "records": [
            {"id": 1, "password": "oops"},
            {"id": 2, "title": "safe"},
        ]
    }
    found = _find_credentials_recursive(response)
    assert "root.records[0].password" in found
