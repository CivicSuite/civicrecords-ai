from pydantic import model_validator
from pydantic_settings import BaseSettings

APP_VERSION = "1.0.1"

_INSECURE_SECRETS = {"CHANGE-ME", "CHANGE-ME-generate-with-openssl-rand-hex-32", ""}


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


settings = Settings()
