import re
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_identifier(value: str, field_name: str) -> str:
    if not _IDENTIFIER_RE.match(value):
        raise ValueError(
            f"{field_name} must be a valid SQL identifier "
            f"(letters, digits, underscores; must start with letter or underscore)"
        )
    return value


class ODBCConfig(BaseModel):
    connector_type: Literal["odbc"] = "odbc"

    connection_string: str  # credential — omit from GET responses
    table_name: str
    pk_column: str
    modified_column: Optional[str] = None
    columns: Optional[list[str]] = None   # None = SELECT *

    batch_size: int = Field(default=500, ge=1, le=10_000)
    max_row_bytes: int = Field(default=10_485_760, ge=1)  # 10MB

    @field_validator("table_name")
    @classmethod
    def validate_table_name(cls, v: str) -> str:
        return _validate_identifier(v, "table_name")

    @field_validator("pk_column")
    @classmethod
    def validate_pk_column(cls, v: str) -> str:
        return _validate_identifier(v, "pk_column")

    @field_validator("modified_column")
    @classmethod
    def validate_modified_column(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return _validate_identifier(v, "modified_column")
        return v

    @field_validator("columns")
    @classmethod
    def validate_columns(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is not None:
            return [_validate_identifier(col, f"columns[{i}]") for i, col in enumerate(v)]
        return v

    @field_validator("connection_string")
    @classmethod
    def _reject_ssrf_targets(cls, v: str) -> str:
        # T2C — block loopback / RFC1918 / link-local / localhost by default;
        # CONNECTOR_HOST_ALLOWLIST is the narrow explicit override. Fails closed
        # if no Server/Host/Data Source field is parseable.
        from app.config import settings
        from app.security.host_validator import validate_odbc_connection_string
        validate_odbc_connection_string(v, settings.connector_host_allowlist)
        return v
