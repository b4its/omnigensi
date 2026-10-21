import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict


class AgentBase(BaseModel):
    name: str = Field(..., max_length=120)
    avatar_code: str = Field(default="cyber-bot-01", max_length=50)
    role: str = Field(..., max_length=150)
    goal: str
    backstory: str
    node_type: Literal["worker", "reviewer", "supervisor"] = "worker"
    model_name: str = Field(..., max_length=150)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, gt=0)
    tools_config: List[str] = Field(default_factory=list)
    require_device_approval: bool = False


class AgentCreate(AgentBase):
    provider_id: uuid.UUID


class AgentUpdate(BaseModel):
    provider_id: Optional[uuid.UUID] = None
    name: Optional[str] = None
    avatar_code: Optional[str] = None
    role: Optional[str] = None
    goal: Optional[str] = None
    backstory: Optional[str] = None
    node_type: Optional[Literal["worker", "reviewer", "supervisor"]] = None
    model_name: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    tools_config: Optional[List[str]] = None
    require_device_approval: Optional[bool] = None


class AgentResponse(AgentBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider_id: uuid.UUID
    provider_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
