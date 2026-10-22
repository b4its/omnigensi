import uuid
from datetime import datetime
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"
    # The history endpoints filter by workflow/status and always sort by
    # started_at, so these columns must be indexed.
    __table_args__ = (
        Index("ix_workflow_executions_workflow_id", "workflow_id"),
        Index("ix_workflow_executions_status", "status"),
        Index("ix_workflow_executions_started_at", "started_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending"
    )  # 'pending', 'running', 'waiting_approval', 'completed', 'failed'
    task_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    final_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Structured failure reason. Errors used to be concatenated into
    # final_output, which made them indistinguishable from real content.
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # True when at least one agent had to emit simulated content because its
    # provider call failed.
    simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    generated_files: Mapped[list] = mapped_column(JSONB, default=list)
    execution_logs: Mapped[list] = mapped_column(JSONB, default=list)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(
        Numeric(10, 6), default=0.0
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    workflow: Mapped["Workflow"] = relationship(
        "Workflow", back_populates="executions"
    )
