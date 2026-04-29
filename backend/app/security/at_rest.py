"""Compatibility wrapper for shared at-rest encryption primitives."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet

from app.config import settings
from civiccore.security import AtRestDecryptionError, decrypt_json as _decrypt_json
from civiccore.security import encrypt_json as _encrypt_json
from civiccore.security import is_encrypted


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    """Build and cache a Fernet instance from the configured key."""

    return Fernet(settings.encryption_key.encode("ascii"))


def encrypt_json(obj: dict) -> dict:
    return _encrypt_json(obj, encryption_key=settings.encryption_key)


def decrypt_json(payload: Any) -> dict:
    return _decrypt_json(payload, encryption_key=settings.encryption_key)


__all__ = [
    "AtRestDecryptionError",
    "_get_fernet",
    "decrypt_json",
    "encrypt_json",
    "is_encrypted",
]
