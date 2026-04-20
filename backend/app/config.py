from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings

APP_VERSION = "1.1.0"

_INSECURE_SECRETS = {"CHANGE-ME", "CHANGE-ME-generate-with-openssl-rand-hex-32", ""}

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
    chat_model: str = "gemma4:26b"
    vision_model: str = "gemma4:26b"
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
    connector_host_allowlist: list[str] = []

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
