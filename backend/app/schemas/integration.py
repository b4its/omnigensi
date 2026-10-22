"""Pydantic schemas for external project integration management and external API consumption."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class IntegrationClientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120, description="Project or client name")
    description: Optional[str] = Field(None, max_length=500, description="Brief description")
    target_url: str = Field(..., max_length=500, description="Target base URL (e.g. http://localhost:8208/)")
    health_endpoint: str = Field("/", max_length=255, description="Relative health check or ping endpoint")
    is_active: bool = Field(True, description="Whether this integration client is active")
    allowed_models: List[str] = Field(default_factory=lambda: ["*"], description="Allowed model IDs or ['*']")
    allowed_workflows: List[str] = Field(default_factory=lambda: ["*"], description="Allowed workflow IDs or ['*']")
    allowed_endpoints: List[str] = Field(default_factory=lambda: ["*"], description="Allowed endpoint tags or ['*']")


class IntegrationClientUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    description: Optional[str] = Field(None, max_length=500)
    target_url: Optional[str] = Field(None, max_length=500)
    health_endpoint: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None
    allowed_models: Optional[List[str]] = None
    allowed_workflows: Optional[List[str]] = None
    allowed_endpoints: Optional[List[str]] = None


class IntegrationClientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: Optional[str] = None
    target_url: str
    health_endpoint: str
    api_key: str
    is_active: bool
    allowed_models: List[str] = Field(default_factory=list)
    allowed_workflows: List[str] = Field(default_factory=list)
    allowed_endpoints: List[str] = Field(default_factory=list)
    status: str
    last_status_code: Optional[int] = None
    last_latency_ms: Optional[int] = None
    last_checked_at: Optional[datetime] = None
    last_error: Optional[str] = None
    target_server: Optional[str] = None
    last_handshake_at: Optional[datetime] = None
    inbound_requests_count: int = 0
    extra_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class IntegrationProbeResult(BaseModel):
    client_id: uuid.UUID
    name: str
    target_url: str
    full_url: str
    status: str  # online, offline, degraded
    status_code: Optional[int] = None
    latency_ms: Optional[int] = None
    server_header: Optional[str] = None
    error: Optional[str] = None
    headers: Dict[str, str] = Field(default_factory=dict)
    checked_at: datetime


class ExternalChatMessage(BaseModel):
    role: str = Field(..., description="Message role (user, assistant, system)")
    content: str = Field(..., description="Message content")


class ExternalChatRequest(BaseModel):
    messages: List[ExternalChatMessage] = Field(..., min_length=1)
    model: Optional[str] = Field(None, description="Model ID to use (falls back to provider default)")
    provider_id: Optional[uuid.UUID] = Field(None, description="Optional specific provider ID")
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(2048, ge=1, le=8192)
    stream: bool = Field(False, description="Stream via SSE or return single JSON completion")


class ExternalChatChoice(BaseModel):
    index: int = 0
    message: ExternalChatMessage
    finish_reason: str = "stop"


class ExternalChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    model: str
    client: str
    choices: List[ExternalChatChoice]
    latency_ms: int


class ExternalHandshakeResponse(BaseModel):
    status: str = "connected"
    client_id: uuid.UUID
    client_name: str
    target_url: str
    omnigensi_version: str
    allowed_models: List[str]
    available_models: List[Dict[str, Any]]
    timestamp: datetime
