import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class ExecutionCreate(BaseModel):
    task_prompt: str = Field(..., min_length=1)


class GeneratedFileInfo(BaseModel):
    filename: str
    filepath: str
    file_type: str
    size_bytes: int
    content_base64: Optional[str] = None
    created_at: str


class ExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_id: uuid.UUID
    status: str
    task_prompt: str
    final_output: Optional[str] = None
    generated_files: List[Dict[str, Any]] = Field(default_factory=list)
    execution_logs: List[Dict[str, Any]] = Field(default_factory=list)
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    started_at: datetime
    completed_at: Optional[datetime] = None


class ToolApprovalRequest(BaseModel):
    tool_call_id: str
    approved: bool
    notes: Optional[str] = None
