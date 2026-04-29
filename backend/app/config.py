from typing import Literal
from typing import Annotated

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode

APP_VERSION = "1.4.1"

_INSECURE_SECRETS = {"CHANGE-ME", "CHANGE-ME-generate-with-openssl-rand-hex-32", ""}

# T6 / ENG-001 — at-rest encryption placeholder for ENCRYPTION_KEY.
# Any value in this set triggers the fail-fast startup check. The actual
# entropy requirement (44-char URL-safe base64) is enforced by Fernet
# itself when the Settings validator tries to build a Fernet instance —
# that catches truncated, padded, or otherwise malformed keys.
_INSECURE_ENCRYPTION_KEYS = {
    "",
    "CHANGE-ME",
    "CHANGE-ME-generate-with-fernet-generate-key",
}

_INSECURE_PASSWORDS = frozenset({
    "CHANGE-ME",
    "CHANGE-ME-on-first-login",
    "password",
    "Password",
    "PASSWORD",
    "admin",
    "Admin",
    "admin123",
    "Admin123",
    "changeme",
    "ChangeMe",
    "12345678",
    "123456789",
    "1234567890",
    "qwertyuiop",
    "letmein",
    "welcome",
    "Welcome1",
})

_MIN_PASSWORD_LEN = 12


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://civicrecords:civicrecords@postgres:5432/civicrecords"
    jwt_secret: str = "CHANGE-ME"
    jwt_lifetime_seconds: int = 3600
    first_admin_email: str = "admin@example.gov"
    first_admin_password: str = "CHANGE-ME"
    ollama_base_url: str = "http://ollama:11434"
    redis_url: str = "redis://redis:6379/0"
    audit_retention_days: int = 1095
    cors_origins: list[str] = ["http://localhost:8080"]
    embedding_model: str = "nomic-embed-text"
    # T5C: gemma4:e4b is the single truthful default across runtime-config surfaces,
    # matching installer picker default. Tier 5 Blocker 1 resolution 2026-04-21.
    chat_model: str = "gemma4:e4b"
    vision_model: str = "gemma4:e4b"
    # SMTP settings for notification email delivery
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "noreply@civicrecords.local"
    smtp_use_tls: bool = True

    # T2C — explicit narrow allowlist for connector hosts that would otherwise be
    # blocked by the SSRF validator (loopback / RFC1918 / link-local / localhost).
    # Empty by default. No wildcard support, no "disable all" escape hatch.
    connector_host_allowlist: Annotated[list[str], NoDecode] = []

    # T5D — install-time portal switch. Locked B4=(b) minimal public surface.
    # "private" (default): staff-only posture. /auth/register is not mounted
    #   and returns 404. No public routes are reachable. UserRole.PUBLIC is
    #   defined in code but is not assignable via self-registration.
    # "public": exposes the minimal public surface — public landing page,
    #   resident-registration path, and an authenticated records-request
    #   submission form for UserRole.PUBLIC users. Per Scott's 2026-04-22
    #   Option A decision, anonymous walk-up submission is NOT supported;
    #   residents must register (creating a UserRole.PUBLIC account) and
    #   sign in before submitting a records request.
    # Any other value raises at startup via the Literal + field_validator.
    portal_mode: Literal["public", "private"] = "private"

    # T6 / ENG-001 — at-rest encryption key for `data_sources.connection_config`.
    # Fernet-compatible: 44-char URL-safe base64 encoding a 32-byte key.
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # Validated at startup by `check_encryption_key` (below); insecure
    # defaults trigger a fail-fast error with remediation. In `testing=True`
    # mode the validator short-circuits and tests use a fixed deterministic
    # key set in `backend/tests/conftest.py`.
    encryption_key: str = "CHANGE-ME-generate-with-fernet-generate-key"

    testing: bool = False

    model_config = {"env_file": ".env", "extra": "ignore"}

    @model_validator(mode="after")
    def check_jwt_secret(self):
        if self.testing:
            return self
        if self.jwt_secret in _INSECURE_SECRETS:
            raise ValueError(
                "JWT_SECRET is set to an insecure default. "
                "Generate a proper secret: openssl rand -hex 32"
            )
        if len(self.jwt_secret) < 32:
            raise ValueError(
                f"JWT_SECRET must be at least 32 characters (got {len(self.jwt_secret)}). "
                "Generate one with: openssl rand -hex 32"
            )
        return self

    @field_validator("connector_host_allowlist", mode="before")
    @classmethod
    def _parse_allowlist_csv(cls, v):
        # Accept CSV strings from env (e.g. "host1,10.0.0.5") in addition to native lists.
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    @field_validator("portal_mode", mode="before")
    @classmethod
    def _normalize_portal_mode(cls, v):
        # Normalize case and whitespace so "Public", " public ", "PRIVATE"
        # all resolve; Literal["public","private"] then enforces the final
        # allowlist. Any other value raises pydantic ValidationError at
        # startup, which is what we want.
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @model_validator(mode="after")
    def check_encryption_key(self):
        """T6 / ENG-001 — validate the at-rest encryption key at startup.

        Rejects insecure defaults with an actionable error. Then attempts
        to build a real ``cryptography.fernet.Fernet`` instance — that call
        catches truncated, padded, or otherwise malformed keys (Fernet
        expects exactly 44 URL-safe base64 characters encoding 32 bytes).
        Short-circuits in ``testing=True`` mode; tests set a fixed key in
        ``backend/tests/conftest.py`` before Settings is imported.
        """
        if self.testing:
            return self
        key = self.encryption_key or ""
        if key in _INSECURE_ENCRYPTION_KEYS:
            raise ValueError(
                "ENCRYPTION_KEY is set to an insecure default. "
                "Generate a proper key:\n"
                "  python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"\n"
                "Back the key up SEPARATELY from the database — losing it "
                "means every saved data-source `connection_config` becomes unreadable."
            )
        try:
            # Deferred import so Settings can be imported without the
            # cryptography package being resolvable (e.g. in lint paths).
            from cryptography.fernet import Fernet

            Fernet(key.encode("ascii"))
        except Exception as exc:  # ValueError, UnicodeEncodeError, binascii.Error
            raise ValueError(
                f"ENCRYPTION_KEY is not a valid Fernet key: {exc}. "
                "It must be 44 URL-safe base64 characters encoding a 32-byte key. "
                "Regenerate with: "
                "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            ) from exc
        return self

    @model_validator(mode="after")
    def check_first_admin_password(self):
        if self.testing:
            return self
        pw = self.first_admin_password or ""
        if pw in _INSECURE_PASSWORDS:
            raise ValueError(
                "FIRST_ADMIN_PASSWORD is set to an insecure placeholder or common value. "
                "Set it to a strong password (at least 12 characters, not in the common "
                "blocklist). On install, the install scripts can generate one for you."
            )
        if len(pw) < _MIN_PASSWORD_LEN:
            raise ValueError(
                f"FIRST_ADMIN_PASSWORD must be at least {_MIN_PASSWORD_LEN} characters "
                f"(got {len(pw)}). Set a strong value before starting the app."
            )
        return self


settings = Settings()
