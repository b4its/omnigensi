"""Schemas for the interactive AI chat console.

The chat console lets an operator talk to any model exposed by a registered
provider. Model selection is driven by the provider registry that the model
sync populates, so the picker always reflects what the provider actually
reports.
"""

import uuid
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(..., max_length=100_000)


class ChatModelOption(BaseModel):
    """One selectable model, tied to the provider that serves it."""

    provider_id: uuid.UUID
    provider_name: str
    model_id: str
    display_name: Optional[str] = None
    context_length: Optional[int] = None
    is_default: bool = False
    is_available: bool = True


class ChatModelsResponse(BaseModel):
    models: List[ChatModelOption]


class ChatCompletionRequest(BaseModel):
    provider_id: uuid.UUID
    model_id: str = Field(..., min_length=1, max_length=255)
    messages: List[ChatMessage] = Field(..., min_length=1)
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=2048, ge=1, le=32000)


class ChatCompletionResponse(BaseModel):
    provider_id: uuid.UUID
    model_id: str
    content: str
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    latency_ms: int = 0
