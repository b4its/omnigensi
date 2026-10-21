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


class ProviderCreate(ProviderBase):
    api_key: str = Field(default="", description="Plaintext API Key to be encrypted")


class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    provider_type: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    default_headers: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


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
