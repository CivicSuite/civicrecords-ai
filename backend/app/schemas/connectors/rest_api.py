from typing import Literal, Optional
from pydantic import AnyHttpUrl, BaseModel, Field, field_validator, model_validator


class RestApiConfig(BaseModel):
    connector_type: Literal["rest_api"] = "rest_api"

    # Connection
    base_url: AnyHttpUrl
    endpoint_path: str = Field(default="/", description="Path appended to base_url")

    # Auth
    auth_method: Literal["none", "api_key", "bearer", "oauth2", "basic"]
    api_key: Optional[str] = None          # credential — omit from GET responses
    key_location: Literal["header", "query"] = "header"
    key_header: str = "X-API-Key"
    token: Optional[str] = None            # bearer token — credential
    client_id: Optional[str] = None
    client_secret: Optional[str] = None   # credential
    token_url: Optional[AnyHttpUrl] = None
    username: Optional[str] = None
    password: Optional[str] = None        # credential

    # Pagination
    pagination_style: Literal["none", "page", "offset", "cursor"] = "none"
    page_param: str = "page"
    offset_param: str = "offset"
    limit_param: str = "limit"
    page_size: int = Field(default=100, ge=1, le=10_000)
    cursor_field: str = "next"

    # Response
    response_format: Literal["json", "xml", "csv"] = "json"
    results_field: Optional[str] = None   # JSON path to records array

    # Idempotency (P6a)
    data_key: Optional[str] = None          # dotted path to logical record; None = root object
    id_field: str = "id"                    # field within each list element used as record ID
    envelope_excludes: list[str] = []       # reserved for v2 — not used in v1

    # Incremental sync
    since_field: Optional[str] = None
    since_format: str = "%Y-%m-%dT%H:%M:%SZ"

    # Limits
    max_records: int = Field(default=10_000, ge=1)
    max_response_bytes: int = Field(default=52_428_800, ge=1)  # 50MB

    @model_validator(mode="after")
    def _cursor_requires_json(self) -> "RestApiConfig":
        if self.pagination_style == "cursor" and self.response_format != "json":
            raise ValueError(
                "pagination_style='cursor' requires response_format='json'"
            )
        return self

    @field_validator("base_url", "token_url")
    @classmethod
    def _reject_ssrf_targets(cls, v):
        # T2C — block loopback / RFC1918 / link-local / localhost by default;
        # CONNECTOR_HOST_ALLOWLIST is the narrow explicit override for
        # legitimate on-prem targets.
        if v is None:
            return v
        from app.config import settings
        from app.security.host_validator import validate_url_host
        validate_url_host(str(v), settings.connector_host_allowlist)
        return v
