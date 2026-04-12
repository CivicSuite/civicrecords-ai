import uuid
from datetime import datetime
from sqlalchemy import DateTime, String, Text, Integer, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.user import Base


class SystemCatalog(Base):
    __tablename__ = "system_catalog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(String(100))
    function: Mapped[str] = mapped_column(String(200))
    vendor_name: Mapped[str] = mapped_column(String(200))
    vendor_version: Mapped[str | None] = mapped_column(String(50))
    access_protocol: Mapped[str] = mapped_column(String(50))
    data_shape: Mapped[str] = mapped_column(String(50))
    common_record_types: Mapped[dict] = mapped_column(JSONB, default=list)
    redaction_tier: Mapped[int] = mapped_column(Integer, default=1)
    discovery_hints: Mapped[dict] = mapped_column(JSONB, default=dict)
    connector_template_id: Mapped[int | None] = mapped_column(Integer)
    catalog_version: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ConnectorTemplate(Base):
    __tablename__ = "connector_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor_name: Mapped[str] = mapped_column(String(200))
    protocol: Mapped[str] = mapped_column(String(50))
    auth_method: Mapped[str] = mapped_column(String(50))
    # oauth2/odbc/api_key/service_account/none
    config_schema: Mapped[dict] = mapped_column(JSONB, default=dict)
    default_sync_schedule: Mapped[str | None] = mapped_column(String(50))
    default_rate_limit: Mapped[int | None] = mapped_column(Integer)
    redaction_tier: Mapped[int] = mapped_column(Integer, default=1)
    setup_instructions: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    catalog_version: Mapped[str] = mapped_column(String(20))
