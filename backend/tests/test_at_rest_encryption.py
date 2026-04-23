"""T6 / ENG-001 — at-rest encryption of ``data_sources.connection_config``.

Covers:

1. :mod:`app.security.at_rest` unit tests — encrypt/decrypt round-trip,
   envelope shape, invalid-token rejection, version dispatch,
   ``is_encrypted`` detector.
2. Startup config validator — :meth:`Settings.check_encryption_key`
   rejects insecure defaults and malformed keys in non-testing mode.
3. End-to-end encryption through the ORM — admin creates a data source
   via the API → raw SQL read confirms the column cell is the v1
   envelope → admin GET round-trips back to plaintext.
4. Migration idempotency — ``is_encrypted`` distinguishes pre-T6
   plaintext from v1 envelope correctly.
"""
from __future__ import annotations

import json
import uuid

import pytest
from cryptography.fernet import Fernet
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import text

from app.config import Settings
from app.models.document import SourceType
from app.security.at_rest import (
    AtRestDecryptionError,
    decrypt_json,
    encrypt_json,
    is_encrypted,
)


# --------------------------------------------------------------------------
# 1. Helper-module unit tests (no DB, no HTTP)
# --------------------------------------------------------------------------

def test_encrypt_decrypt_roundtrip_preserves_dict():
    payload = {"api_key": "secret-value", "base_url": "https://example.com", "depth": 3}
    envelope = encrypt_json(payload)
    assert is_encrypted(envelope)
    assert decrypt_json(envelope) == payload


def test_encrypt_json_returns_versioned_envelope_shape():
    envelope = encrypt_json({"k": "v"})
    assert set(envelope.keys()) == {"v", "ct"}
    assert envelope["v"] == 1
    assert isinstance(envelope["ct"], str) and len(envelope["ct"]) > 0


def test_encrypt_json_rejects_non_dict_input():
    with pytest.raises(TypeError):
        encrypt_json(["not", "a", "dict"])  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        encrypt_json("scalar string")  # type: ignore[arg-type]


def test_decrypt_json_rejects_missing_version():
    with pytest.raises(AtRestDecryptionError) as exc:
        decrypt_json({"ct": "abc"})
    assert "'v' version field" in str(exc.value)


def test_decrypt_json_rejects_unknown_version():
    with pytest.raises(AtRestDecryptionError) as exc:
        decrypt_json({"v": 999, "ct": "abc"})
    assert "v=999" in str(exc.value) or "unknown" in str(exc.value).lower()


def test_decrypt_json_rejects_tampered_ciphertext():
    envelope = encrypt_json({"k": "v"})
    # Flip a character in the middle of the ciphertext.
    tampered = envelope.copy()
    ct = list(tampered["ct"])
    # Middle byte mutation is most likely to land in the AEAD payload.
    ct[len(ct) // 2] = "A" if ct[len(ct) // 2] != "A" else "B"
    tampered["ct"] = "".join(ct)
    with pytest.raises(AtRestDecryptionError) as exc:
        decrypt_json(tampered)
    assert "tampered" in str(exc.value).lower() or "fernet" in str(exc.value).lower()


def test_decrypt_json_rejects_non_dict_payload():
    with pytest.raises(AtRestDecryptionError):
        decrypt_json("not-a-dict")  # type: ignore[arg-type]
    with pytest.raises(AtRestDecryptionError):
        decrypt_json(None)


def test_is_encrypted_true_for_envelope():
    assert is_encrypted({"v": 1, "ct": "anything"}) is True


@pytest.mark.parametrize(
    "value",
    [
        {},  # empty dict
        {"api_key": "plaintext"},
        {"v": 1},  # missing ct
        {"ct": "x"},  # missing v
        {"v": "1", "ct": "x"},  # v is string, not int
        {"v": 1, "ct": 123},  # ct is not string
        "not-a-dict",
        None,
        ["v", 1, "ct", "x"],
    ],
)
def test_is_encrypted_false_for_non_envelope(value):
    assert is_encrypted(value) is False


# --------------------------------------------------------------------------
# 2. Settings.check_encryption_key validator
# --------------------------------------------------------------------------

def test_encryption_key_rejects_insecure_defaults(monkeypatch):
    """Non-testing-mode Settings must reject placeholder keys."""
    monkeypatch.setenv("ENCRYPTION_KEY", "CHANGE-ME")
    with pytest.raises(ValidationError) as exc:
        # testing=False reads ENCRYPTION_KEY as the real
        # runtime value and runs the full validator chain.
        Settings(
            jwt_secret="a" * 64,
            first_admin_password="CivicDev2026!xZ",
            testing=False,
        )
    assert "insecure default" in str(exc.value)


def test_encryption_key_rejects_malformed_key(monkeypatch):
    """Any value Fernet can't ingest must raise at startup."""
    monkeypatch.setenv("ENCRYPTION_KEY", "not-a-valid-fernet-key")
    with pytest.raises(ValidationError) as exc:
        Settings(
            jwt_secret="a" * 64,
            first_admin_password="CivicDev2026!xZ",
            testing=False,
        )
    msg = str(exc.value)
    assert "not a valid Fernet key" in msg or "Fernet" in msg


def test_encryption_key_accepts_real_fernet_key(monkeypatch):
    """A real Fernet.generate_key() output passes validation."""
    real_key = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", real_key)
    s = Settings(
        jwt_secret="a" * 64,
        first_admin_password="CivicDev2026!xZ",
        testing=False,
    )
    assert s.encryption_key == real_key


def test_encryption_key_validator_skipped_in_testing_mode(monkeypatch):
    """testing=True short-circuits the validator entirely."""
    monkeypatch.setenv("ENCRYPTION_KEY", "")
    s = Settings(
        jwt_secret="a" * 64,
        first_admin_password="CivicDev2026!xZ",
        testing=True,
    )
    assert s.encryption_key == ""  # validator didn't run


# --------------------------------------------------------------------------
# 3. End-to-end encryption through the ORM + DB
# --------------------------------------------------------------------------
#
# Admin creates a DataSource via the API → read the raw JSONB cell via
# SELECT → it's the v1 envelope (NOT the plaintext dict). Admin GET on
# the same row round-trips back to the plaintext dict.

async def test_admin_create_writes_encrypted_envelope_to_db(
    client: AsyncClient, admin_token: str, db_session
):
    payload = {
        "name": f"T6 round-trip {uuid.uuid4().hex[:6]}",
        "source_type": "file_system",
        "connection_config": {"path": "/data/t6-roundtrip", "api_key": "super-secret-123"},
    }
    resp = await client.post(
        "/datasources/",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=payload,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    ds_id = body["id"]
    # API response DOES contain the plaintext dict (admin-only DataSourceAdminRead)
    assert body["connection_config"] == payload["connection_config"]

    # Raw DB read — the cell should be the v1 envelope, NOT plaintext.
    # Go straight through the session, bypassing ORM attribute mapping.
    result = await db_session.execute(
        text("SELECT connection_config FROM data_sources WHERE id = :id"),
        {"id": ds_id},
    )
    raw = result.scalar_one()
    assert is_encrypted(raw), (
        f"Expected v1 envelope in DB, got {type(raw).__name__}: {raw!r}. "
        "EncryptedJSONB TypeDecorator did not encrypt on write."
    )
    # Proving the ciphertext actually protects the secret: the raw JSONB
    # blob, when JSON-serialized, MUST NOT contain the plaintext secret
    # anywhere.
    assert "super-secret-123" not in json.dumps(raw), (
        "Plaintext secret leaked into the encrypted envelope — something "
        "bypassed the encryption path."
    )


async def test_admin_get_decrypts_back_to_plaintext(
    client: AsyncClient, admin_token: str
):
    payload = {
        "name": f"T6 decrypt-read {uuid.uuid4().hex[:6]}",
        "source_type": "rest_api",
        "connection_config": {"base_url": "https://example.com/api", "token": "bearer-xyz"},
    }
    create = await client.post(
        "/datasources/",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=payload,
    )
    assert create.status_code == 201, create.text
    ds_id = create.json()["id"]

    # PATCH is the response path we know returns DataSourceAdminRead
    # (including connection_config for admin). Issue a no-op update to
    # exercise the round-trip.
    update = await client.patch(
        f"/datasources/{ds_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"connection_config": payload["connection_config"]},
    )
    assert update.status_code == 200, update.text
    # The response reflects decrypted data.
    assert update.json()["connection_config"] == payload["connection_config"]


# --------------------------------------------------------------------------
# 4. Migration idempotency smoke test
# --------------------------------------------------------------------------
#
# Encrypting an already-encrypted envelope should pass through unchanged
# (via the EncryptedJSONB.process_bind_param idempotent check). The
# ``is_encrypted`` detector is the single source of truth for both the
# TypeDecorator and the alembic migration.

def test_encrypted_envelope_is_stable_under_reencryption_check():
    original = {"api_key": "x", "base_url": "y"}
    env1 = encrypt_json(original)
    assert is_encrypted(env1)
    # Simulate what EncryptedJSONB.process_bind_param does on an
    # already-encrypted value — it should NOT re-wrap.
    from app.models.document import EncryptedJSONB
    td = EncryptedJSONB()
    bound = td.process_bind_param(env1, None)
    assert bound == env1  # no re-wrapping
    # Round-trip through decrypt still works.
    assert decrypt_json(td.process_bind_param(original, None)) == original
