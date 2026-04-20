"""Host validator for connector URLs — SSRF protection at schema-validation time.

Blocks admin-supplied connector destinations that point at internal/loopback/link-local/
RFC1918 ranges, which an attacker could exploit to reach IMDS, internal services, or
other tenants. The block is applied at Pydantic schema-validation time so an attempted
save of a poisoned config is rejected before it ever reaches a live HTTP client.

Only literal IP hosts are matched against CIDR blocks; hostname strings that are not
literal IPs are accepted unless they exactly match the hostname blocklist (e.g.
``localhost``). Deliberate: DNS is not resolved here because resolution results can
vary between validation time and the time the connector actually dials, and because
validators must be deterministic and fast.

Explicit override: ``CONNECTOR_HOST_ALLOWLIST`` (comma-separated hosts). Empty by
default. No wildcard support, no "disable all" escape hatch — operators must list the
exact hosts they intend to reach.
"""
from __future__ import annotations

import ipaddress
from typing import Iterable
from urllib.parse import urlparse

_BLOCKED_HOSTNAMES = frozenset({"localhost"})

_BLOCKED_NETWORKS: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = (
    ipaddress.ip_network("127.0.0.0/8"),       # loopback IPv4
    ipaddress.ip_network("169.254.0.0/16"),    # link-local / IMDS
    ipaddress.ip_network("10.0.0.0/8"),        # RFC1918
    ipaddress.ip_network("172.16.0.0/12"),     # RFC1918
    ipaddress.ip_network("192.168.0.0/16"),    # RFC1918
    ipaddress.ip_network("0.0.0.0/32"),        # unspecified IPv4
    ipaddress.ip_network("::1/128"),           # loopback IPv6
)

_ODBC_HOST_KEYS = frozenset({"server", "host", "data source"})

_BLOCK_REASON = (
    "host is in a blocked range (loopback / RFC1918 / link-local / localhost). "
    "Add it to CONNECTOR_HOST_ALLOWLIST if this is an intentional on-prem or "
    "air-gapped target."
)


def _normalize_allowlist(allowlist: Iterable[str]) -> set[str]:
    return {h.strip().lower() for h in allowlist if h and h.strip()}


def is_blocked_host(host: str, allowlist: Iterable[str] = ()) -> bool:
    """Return True if ``host`` is in a blocked range and not on the allowlist.

    Empty/whitespace-only host fails closed (True). Allowlist matches are exact
    (case-insensitive). Non-literal hostnames that are not in the hostname
    blocklist pass.
    """
    if not host or not host.strip():
        return True
    normalized = host.strip().lower()
    allow = _normalize_allowlist(allowlist)
    if normalized in allow:
        return False
    if normalized in _BLOCKED_HOSTNAMES:
        return True
    try:
        ip = ipaddress.ip_address(normalized)
    except ValueError:
        return False
    for net in _BLOCKED_NETWORKS:
        if ip.version == net.version and ip in net:
            return True
    return False


def validate_url_host(url: str, allowlist: Iterable[str] = ()) -> None:
    """Raise ValueError if ``url``'s host is blocked. No-op on pass."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").strip()
    if is_blocked_host(host, allowlist):
        raise ValueError(f"Connector URL {url!r}: {_BLOCK_REASON}")


def extract_odbc_host(connection_string: str) -> str | None:
    """Extract the Server/Host/Data Source field from an ODBC connection string.

    Returns None if no known host key is found. Callers must treat None as
    failure and fail closed — unknown host shapes must not be silently accepted.
    """
    if not connection_string:
        return None
    for part in connection_string.split(";"):
        if "=" not in part:
            continue
        key, _, value = part.partition("=")
        if key.strip().lower() not in _ODBC_HOST_KEYS:
            continue
        value = value.strip()
        if value.startswith("{") and value.endswith("}"):
            value = value[1:-1]
        for sep in (",", ":"):
            if sep in value:
                value = value.split(sep, 1)[0]
        value = value.strip()
        return value or None
    return None


def validate_odbc_connection_string(
    connection_string: str, allowlist: Iterable[str] = ()
) -> None:
    """Raise ValueError if the ODBC connection string's host is blocked or unparseable."""
    host = extract_odbc_host(connection_string)
    if host is None:
        raise ValueError(
            "ODBC connection string does not contain a parseable Server/Host/Data Source "
            "field. Fail-closed: add an explicit Server=... entry before saving."
        )
    if is_blocked_host(host, allowlist):
        raise ValueError(f"ODBC connector host {host!r}: {_BLOCK_REASON}")
