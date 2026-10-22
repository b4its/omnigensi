import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict


class ProviderBase(BaseModel):
    name: str = Field(..., max_length=100)
    provider_type: str = Field(
        ...,
        description="Type: openrouter, litellm, openai, ollama, custom",
        max_length=50,
    )
    base_url: str = Field(..., max_length=255)
    default_headers: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    default_model: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Preselected chat model for agents built on this provider",
    )


class ProviderCreate(ProviderBase):
    api_key: str = Field(default="", description="Plaintext API Key to be encrypted")


class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    provider_type: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    default_headers: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    default_model: Optional[str] = Field(default=None, max_length=255)


class ProviderResponse(ProviderBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    has_api_key: bool = True


class ModelInfo(BaseModel):
    id: str
    name: Optional[str] = None
    context_length: Optional[int] = None
    description: Optional[str] = None
    pricing: Optional[Dict[str, Any]] = None


class ProviderModelResponse(BaseModel):
    """A chat model stored for a provider."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider_id: uuid.UUID
    model_id: str
    display_name: Optional[str] = None
    context_length: Optional[int] = None
    description: Optional[str] = None
    pricing: Dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False
    is_available: bool = True
    created_at: datetime
    updated_at: datetime


class ModelSyncResult(BaseModel):
    """Outcome of the "auto-add models" operation."""

    ok: bool
    provider_id: uuid.UUID
    discovered: int = Field(ge=0, description="Models reported by the provider")
    added: int = Field(ge=0)
    updated: int = Field(ge=0)
    marked_unavailable: int = Field(ge=0)
    removed: int = Field(
        default=0,
        ge=0,
        description="Rows deleted because they no longer exist upstream (prune only)",
    )
    total_stored: int = Field(ge=0)
    checked_url: Optional[str] = None
    latency_ms: int = 0
    error: Optional[str] = None


class SetDefaultModelRequest(BaseModel):
    """Selects which stored model is the provider default."""

    model_id: str = Field(..., min_length=1, max_length=255)
    verify: bool = Field(
        default=True,
        description=(
            "Run a real chat completion before saving so a model whose upstream "
            "is out of credits or misconfigured cannot become the default. "
            "Set false to save without verifying."
        ),
    )


class ChatTestRequest(BaseModel):
    """Payload for testing a real chat completion."""

    model_id: Optional[str] = Field(
        default=None,
        description="Model to test; falls back to the provider default",
        max_length=255,
    )
    prompt: str = Field(
        default="Reply with the single word: OK",
        min_length=1,
        max_length=2000,
        description="Prompt sent to the model",
    )
    max_tokens: int = Field(default=64, ge=1, le=512)


class ChatTestResult(BaseModel):
    """Result of a chat completion probe."""

    ok: bool
    model_id: str
    response_text: Optional[str] = None
    latency_ms: int = 0
    status_code: Optional[int] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    checked_url: Optional[str] = None
    error: Optional[str] = None


class DraftDiscoveryRequest(BaseModel):
    """Probe a provider that has not been saved yet."""

    base_url: str = Field(..., max_length=255)
    api_key: str = Field(default="")
    provider_type: str = Field(default="custom", max_length=50)


class DraftDiscoveryResponse(BaseModel):
    ok: bool
    models: List[ModelInfo] = Field(default_factory=list)
    checked_url: Optional[str] = None
    latency_ms: int = 0
    error: Optional[str] = None


class DraftChatTestRequest(DraftDiscoveryRequest):
    """Run a chat completion against unsaved credentials."""

    model_id: str = Field(..., min_length=1, max_length=255)
    prompt: str = Field(default="Reply with the single word: OK", min_length=1, max_length=2000)
