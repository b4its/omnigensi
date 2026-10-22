"""Persisted external project integrations and API client credentials.

Allows external applications (e.g. Laravel project "agen xishie") to register,
authenticate via API key, consume AI models/workflows, and have their health
and connectivity status monitored in real time.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class IntegrationClient(Base):
    """An external project registered to hit Omnigensi APIs and be monitored."""

    __tablename__ = "integration_clients"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Target external URL to monitor (e.g. http://localhost:8208/)
    target_url: Mapped[str] = mapped_column(String(500), nullable=False)
    health_endpoint: Mapped[str] = mapped_column(String(255), nullable=False, default="/")

    # API key issued to the external project (e.g. omni_live_...)
    api_key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Scopes and permissions: models, workflows, endpoints allowed
    allowed_models: Mapped[list] = mapped_column(JSONB, default=lambda: ["*"])
    allowed_workflows: Mapped[list] = mapped_column(JSONB, default=lambda: ["*"])
    allowed_endpoints: Mapped[list] = mapped_column(JSONB, default=lambda: ["*"])

    # Outbound monitoring telemetry (Omnigensi -> Target URL)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    last_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_server: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Inbound telemetry (Target project -> Omnigensi API)
    last_handshake_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    inbound_requests_count: Mapped[int] = mapped_column(Integer, default=0)

    # Extra target metadata (headers, runtime info, etc.)
    extra_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
