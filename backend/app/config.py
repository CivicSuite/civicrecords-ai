from typing import Annotated, Literal

from civiccore.security import (
    DEFAULT_INSECURE_FERNET_KEY_VALUES,
    DEFAULT_INSECURE_PASSWORD_VALUES,
    DEFAULT_INSECURE_SECRET_VALUES,
    parse_csv_setting,
    validate_fernet_key_setting,
    validate_password_setting,
    validate_secret_setting,
)
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode

APP_VERSION = "1.4.9"

_INSECURE_SECRETS = DEFAULT_INSECURE_SECRET_VALUES
_INSECURE_ENCRYPTION_KEYS = DEFAULT_INSECURE_FERNET_KEY_VALUES
_INSECURE_PASSWORDS = DEFAULT_INSECURE_PASSWORD_VALUES
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
    # SMTP settings for notification email delivery.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "noreply@civicrecords.local"
    smtp_use_tls: bool = True

    # Empty by default. No wildcard support, no "disable all" escape hatch.
    connector_host_allowlist: Annotated[list[str], NoDecode] = []

    # "private" keeps staff-only posture. "public" exposes the minimal resident portal.
    portal_mode: Literal["public", "private"] = "private"

    # Fernet-compatible key for data_sources.connection_config encrypted JSON envelopes.
    encryption_key: str = "CHANGE-ME-generate-with-fernet-generate-key"

    testing: bool = False

    model_config = {"env_file": ".env", "extra": "ignore"}

    @model_validator(mode="after")
    def check_jwt_secret(self):
        if self.testing:
            return self
        validate_secret_setting(self.jwt_secret, setting_name="JWT_SECRET")
        return self

    @field_validator("connector_host_allowlist", mode="before")
    @classmethod
    def _parse_allowlist_csv(cls, v):
        # Accept CSV strings from env in addition to native lists.
        return parse_csv_setting(v) if isinstance(v, (str, list, tuple, set)) or v is None else v

    @field_validator("portal_mode", mode="before")
    @classmethod
    def _normalize_portal_mode(cls, v):
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @model_validator(mode="after")
    def check_encryption_key(self):
        if self.testing:
            return self
        validate_fernet_key_setting(self.encryption_key, setting_name="ENCRYPTION_KEY")
        return self

    @model_validator(mode="after")
    def check_first_admin_password(self):
        if self.testing:
            return self
        validate_password_setting(
            self.first_admin_password,
            setting_name="FIRST_ADMIN_PASSWORD",
            min_length=_MIN_PASSWORD_LEN,
        )
        return self


settings = Settings()
