import uuid
from datetime import datetime
from sqlalchemy import String, Text, Float, Integer, Boolean, DateTime, ForeignKey, CheckConstraint, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class AgentTemplate(Base):
    __tablename__ = "agent_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("llm_providers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    avatar_code: Mapped[str] = mapped_column(String(50), default="cyber-bot-01")
    role: Mapped[str] = mapped_column(String(150), nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    backstory: Mapped[str] = mapped_column(Text, nullable=False)
    node_type: Mapped[str] = mapped_column(
        String(30),
        CheckConstraint("node_type IN ('worker', 'reviewer', 'supervisor')"),
        nullable=False,
    )
    model_name: Mapped[str] = mapped_column(String(150), nullable=False)
    temperature: Mapped[float] = mapped_column(Float, default=0.7)
    max_tokens: Mapped[int] = mapped_column(Integer, default=4096)
    tools_config: Mapped[list] = mapped_column(JSONB, default=list)
    require_device_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    provider: Mapped["LLMProvider"] = relationship(
        "LLMProvider", back_populates="agents"
    )
