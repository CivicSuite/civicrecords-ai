"""T6 / ENG-001 — at-rest encryption for ``data_sources.connection_config``.

This module provides the primitives that close the at-rest exposure gap
T2B left open: plaintext connector credentials (API keys, ODBC passwords,
IMAP tokens, etc.) sitting in the ``data_sources.connection_config``
JSONB column and therefore visible in ``pg_dump`` output, DB backups,
restored snapshots, and any Postgres superuser session.

Design decisions (Scott-locked 2026-04-23, do not reopen without explicit
re-scoping):

* Single key. One ``ENCRYPTION_KEY`` env var. No MultiFernet,
  no key-rotation program in v1. The versioned envelope (``"v": 1``)
  leaves rotation as a clean v2 addition when needed.
* Fernet (``cryptography.fernet``). AES-128-CBC + HMAC-SHA256,
  authenticated encryption, standard Python primitive. No custom crypto.
* ENG-001 closure = this module + the SQLAlchemy ``TypeDecorator`` that
  wraps it. No audit-log scrub side quest — the audit surface was closed
  in T2B and the pre-T2B scan found no historical plaintext leakage.

Envelope shape (stored in the JSONB column):

.. code-block:: json

    {"v": 1, "ct": "<fernet-token-url-safe-base64>"}

Where ``ct`` is the Fernet token produced by
``Fernet(settings.encryption_key).encrypt(json_bytes)``.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


_ENVELOPE_VERSION = 1


class AtRestDecryptionError(Exception):
    """Raised when a stored envelope cannot be decrypted back to a dict.

    Caller should treat this as a data-integrity issue — either the key
    has changed without a re-encryption pass, the ciphertext has been
    tampered with, or the envelope shape is unknown (a future ``v`` this
    codebase does not know how to decrypt yet).
    """


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    """Build and cache a Fernet instance from the configured key.

    Cached because Fernet construction is trivial but the env lookup +
    validation path is worth skipping on every encrypt/decrypt call. The
    cache is keyed on nothing — each Settings() instance has exactly one
    key for its process lifetime. Tests that swap the key between
    scenarios must call ``_get_fernet.cache_clear()`` explicitly.
    """
    return Fernet(settings.encryption_key.encode("ascii"))


def encrypt_json(obj: dict) -> dict:
    """Encrypt a connection-config dict into the versioned envelope.

    Always returns the envelope shape ``{"v": 1, "ct": "..."}``. The
    input dict is serialized with ``json.dumps(sort_keys=True)`` so the
    ciphertext is deterministic w.r.t. key order (useful for migration
    idempotence checks and diffable fixtures). Fernet itself adds a
    nonce + timestamp, so the actual token still differs between calls
    even for identical input.
    """
    if not isinstance(obj, dict):
        raise TypeError(
            f"encrypt_json expects a dict, got {type(obj).__name__}. "
            "The column contract for data_sources.connection_config is a "
            "JSON object — lists and scalars are not supported."
        )
    plaintext = json.dumps(obj, sort_keys=True).encode("utf-8")
    token = _get_fernet().encrypt(plaintext).decode("ascii")
    return {"v": _ENVELOPE_VERSION, "ct": token}


def decrypt_json(payload: Any) -> dict:
    """Decrypt a stored envelope back into the original dict.

    Dispatches on ``payload["v"]`` so future envelope versions can add
    rotation metadata or alternative ciphers without breaking the v1
    decode path. Anything other than a valid v1 envelope raises
    :class:`AtRestDecryptionError`.
    """
    if not isinstance(payload, dict):
        raise AtRestDecryptionError(
            f"Envelope must be a dict, got {type(payload).__name__}. "
            "The row is likely plaintext and needs a migration pass."
        )
    if "v" not in payload:
        raise AtRestDecryptionError(
            "Envelope is missing the 'v' version field — "
            "the row is likely pre-T6 plaintext and needs a migration pass."
        )
    version = payload["v"]
    if version != _ENVELOPE_VERSION:
        raise AtRestDecryptionError(
            f"Unknown envelope version v={version!r}. "
            f"This codebase only knows how to decrypt v={_ENVELOPE_VERSION}."
        )
    token = payload.get("ct")
    if not isinstance(token, str):
        raise AtRestDecryptionError(
            "Envelope is missing a string 'ct' ciphertext field."
        )
    try:
        plaintext = _get_fernet().decrypt(token.encode("ascii"))
    except InvalidToken as exc:
        raise AtRestDecryptionError(
            "Fernet rejected the ciphertext: either the encryption key "
            "has changed without a re-encryption pass, or the stored "
            "value has been tampered with."
        ) from exc
    return json.loads(plaintext.decode("utf-8"))


def is_encrypted(value: Any) -> bool:
    """Return True if ``value`` already matches the v1 envelope shape.

    Used by the Alembic migration to detect already-encrypted rows so the
    upgrade path is idempotent — re-running the migration on a partially
    or fully encrypted table is a no-op per row.
    """
    return (
        isinstance(value, dict)
        and value.get("v") == _ENVELOPE_VERSION
        and isinstance(value.get("ct"), str)
    )
