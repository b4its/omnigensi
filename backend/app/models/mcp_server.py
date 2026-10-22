"""Persisted MCP server registrations.

Registrations were previously in-memory only, so every restart silently
dropped servers an operator had configured through the UI.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MCPServer(Base):
    """A configured Model Context Protocol server."""

    __tablename__ = "mcp_servers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    server_type: Mapped[str] = mapped_column(String(20), nullable=False, default="stdio")
    command: Mapped[str | None] = mapped_column(String(255), nullable=True)
    args: Mapped[list] = mapped_column(JSONB, default=list)
    env: Mapped[dict] = mapped_column(JSONB, default=dict)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Built-in bridges are recreated on startup and must not be removable
    # permanently; tracking them lets a delete be remembered.
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
