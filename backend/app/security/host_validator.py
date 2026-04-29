"""Compatibility re-export for shared connector-host validation primitives."""

from civiccore.security import (
    BLOCK_REASON as _BLOCK_REASON,
    BLOCKED_HOSTNAMES as _BLOCKED_HOSTNAMES,
    BLOCKED_NETWORKS as _BLOCKED_NETWORKS,
    ODBC_HOST_KEYS as _ODBC_HOST_KEYS,
    extract_odbc_host,
    is_blocked_host,
    normalize_allowlist as _normalize_allowlist,
    validate_odbc_connection_string,
    validate_url_host,
)

__all__ = [
    "_BLOCK_REASON",
    "_BLOCKED_HOSTNAMES",
    "_BLOCKED_NETWORKS",
    "_ODBC_HOST_KEYS",
    "_normalize_allowlist",
    "extract_odbc_host",
    "is_blocked_host",
    "validate_odbc_connection_string",
    "validate_url_host",
]
