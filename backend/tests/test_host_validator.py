"""Unit tests for backend.app.security.host_validator (T2C SSRF hardening).

Every blocked range listed in the remediation plan is exercised here, plus the
allowlist override, plus the ODBC connection-string parser and its fail-closed
behavior on ambiguous input.
"""
import pytest

from app.security.host_validator import (
    extract_odbc_host,
    is_blocked_host,
    validate_odbc_connection_string,
    validate_url_host,
)


# ───────────────────────────── is_blocked_host ─────────────────────────────
@pytest.mark.parametrize(
    "host,blocked",
    [
        # Loopback IPv4 — 127.0.0.0/8
        ("127.0.0.1", True),
        ("127.0.0.254", True),
        ("127.1.2.3", True),
        ("127.255.255.254", True),
        # Link-local / IMDS — 169.254.0.0/16
        ("169.254.169.254", True),
        ("169.254.0.1", True),
        ("169.254.255.255", True),
        # Loopback IPv6 — ::1/128
        ("::1", True),
        # Wildcard IPv4 — 0.0.0.0
        ("0.0.0.0", True),
        # Hostname blocks — localhost (case-insensitive)
        ("localhost", True),
        ("LOCALHOST", True),
        ("Localhost", True),
        # RFC1918 — 10.0.0.0/8
        ("10.0.0.1", True),
        ("10.255.255.255", True),
        # RFC1918 — 172.16.0.0/12
        ("172.16.0.1", True),
        ("172.20.0.1", True),
        ("172.31.255.254", True),
        # RFC1918 — 192.168.0.0/16
        ("192.168.0.1", True),
        ("192.168.255.255", True),
        # Pass-through — public IPs
        ("8.8.8.8", False),
        ("1.1.1.1", False),
        ("93.184.216.34", False),
        # Pass-through — non-literal hostnames
        ("api.example.com", False),
        ("public.service.gov", False),
        ("prod.internal-but-public.example.org", False),
        # Boundary — adjacent to blocked ranges but not in them
        ("9.255.255.255", False),
        ("11.0.0.0", False),
        ("172.15.255.255", False),
        ("172.32.0.0", False),
        ("192.167.255.255", False),
        ("192.169.0.0", False),
        ("128.0.0.0", False),
    ],
)
def test_is_blocked_host_without_allowlist(host, blocked):
    assert is_blocked_host(host) is blocked, f"{host}: expected blocked={blocked}"


def test_empty_or_whitespace_host_fails_closed():
    assert is_blocked_host("") is True
    assert is_blocked_host("   ") is True


# ───────────────────────────── allowlist override ─────────────────────────────
def test_allowlist_exact_match_bypasses_block():
    assert is_blocked_host("10.0.0.5", allowlist=["10.0.0.5"]) is False
    assert is_blocked_host("localhost", allowlist=["localhost"]) is False
    assert is_blocked_host("192.168.1.1", allowlist=["192.168.1.1"]) is False


def test_allowlist_case_insensitive():
    assert is_blocked_host("LOCALHOST", allowlist=["localhost"]) is False
    assert is_blocked_host("localhost", allowlist=["LOCALHOST"]) is False


def test_allowlist_does_not_admit_other_blocked_hosts():
    assert is_blocked_host("10.0.0.6", allowlist=["10.0.0.5"]) is True
    assert is_blocked_host("169.254.169.254", allowlist=["10.0.0.5"]) is True


def test_allowlist_rejects_wildcard_literal():
    # Allowlist is not interpreted as a glob; "*" is not a valid bypass
    assert is_blocked_host("10.0.0.5", allowlist=["*"]) is True
    assert is_blocked_host("localhost", allowlist=["*"]) is True


def test_empty_allowlist_entries_ignored():
    # Blank / whitespace-only entries must not accidentally match empty-host input
    assert is_blocked_host("10.0.0.5", allowlist=["", "   "]) is True


# ───────────────────────────── validate_url_host ─────────────────────────────
@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",          # AWS IMDS
        "https://localhost/api",
        "http://127.0.0.1:8000/",
        "http://10.0.0.1/",
        "http://172.16.0.1/",
        "http://192.168.1.1/",
        "http://0.0.0.0/",
    ],
)
def test_validate_url_host_rejects_blocked(url):
    with pytest.raises(ValueError, match="blocked range"):
        validate_url_host(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://api.example.com/",
        "http://8.8.8.8/",
        "https://public.service.gov/data",
    ],
)
def test_validate_url_host_allows_public(url):
    validate_url_host(url)  # must not raise


def test_validate_url_host_respects_allowlist():
    validate_url_host("http://10.0.0.5/", allowlist=["10.0.0.5"])
    with pytest.raises(ValueError, match="blocked range"):
        validate_url_host("http://10.0.0.6/", allowlist=["10.0.0.5"])


# ───────────────────────────── extract_odbc_host ─────────────────────────────
@pytest.mark.parametrize(
    "conn_str,expected_host",
    [
        ("Driver={PostgreSQL};Server=db.example.com;Database=foo", "db.example.com"),
        ("Server=10.0.0.5;Database=x", "10.0.0.5"),
        ("SERVER=db.example.com;UID=a;PWD=b", "db.example.com"),
        ("host=db.example.com;Port=5432", "db.example.com"),
        # Port suffix (comma-delimited, SQL Server style)
        ("Server=db.example.com,1433;Database=x", "db.example.com"),
        # Port suffix (colon-delimited)
        ("Server=db.example.com:5432;Database=x", "db.example.com"),
        # Braced value
        ("Server={db.example.com};Database=x", "db.example.com"),
        # Data Source alias
        ("Data Source=db.example.com;Initial Catalog=x", "db.example.com"),
    ],
)
def test_extract_odbc_host_parses_known_forms(conn_str, expected_host):
    assert extract_odbc_host(conn_str) == expected_host


@pytest.mark.parametrize(
    "conn_str",
    [
        # No Server/Host/Data Source key
        "Driver={PostgreSQL};Database=foo;UID=a",
        # Empty string
        "",
        # Only DSN name — no host field
        "DSN=mydsn;UID=a;PWD=b",
        # Server key present but empty
        "Server=;Database=x",
    ],
)
def test_extract_odbc_host_returns_none_on_ambiguous(conn_str):
    assert extract_odbc_host(conn_str) is None


# ────────────────── validate_odbc_connection_string ──────────────────
def test_validate_odbc_rejects_blocked_hosts():
    with pytest.raises(ValueError, match="blocked range"):
        validate_odbc_connection_string("Server=127.0.0.1;Database=x")
    with pytest.raises(ValueError, match="blocked range"):
        validate_odbc_connection_string("Server=localhost;Database=x")
    with pytest.raises(ValueError, match="blocked range"):
        validate_odbc_connection_string("Server=192.168.1.1;Database=x")
    with pytest.raises(ValueError, match="blocked range"):
        validate_odbc_connection_string("Server=169.254.169.254;Database=x")


def test_validate_odbc_fails_closed_on_ambiguous():
    with pytest.raises(ValueError, match="parseable Server/Host"):
        validate_odbc_connection_string("Driver={PostgreSQL};Database=x")
    with pytest.raises(ValueError, match="parseable Server/Host"):
        validate_odbc_connection_string("DSN=mydsn")


def test_validate_odbc_respects_allowlist():
    validate_odbc_connection_string(
        "Server=10.0.0.5;Database=x", allowlist=["10.0.0.5"]
    )
    with pytest.raises(ValueError, match="blocked range"):
        validate_odbc_connection_string(
            "Server=10.0.0.6;Database=x", allowlist=["10.0.0.5"]
        )


def test_validate_odbc_allows_public_host():
    validate_odbc_connection_string("Server=db.public.example.com;Database=x")
    validate_odbc_connection_string("Server=8.8.8.8;Database=x")
