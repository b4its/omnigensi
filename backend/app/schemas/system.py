"""Shared system-level API contracts.

These schemas back the endpoints consumed by every client (web UI and the
mobile app) for the same purpose: discovering capabilities, checking health and
keeping error handling consistent across platforms.
"""

import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response for ``GET /health`` and ``GET /api/v1/health``."""

    status: str = Field(examples=["healthy"])
    service: str = Field(examples=["omnigensi-backend"])
    version: str = Field(examples=["2.0.0"])
    workspace_root: str


class ClientConfigResponse(BaseModel):
    """Bootstrap payload for clients (mobile app / web) hitting the API cold.

    Lets a mobile client discover the current API version, the SSE stream path
    template and feature flags instead of hardcoding them per-platform.
    """

    service: str = Field(examples=["omnigensi-backend"])
    version: str
    api_version: str = Field(examples=["v1"])
    api_base_path: str = Field(examples=["/api/v1"])
    base_url: str = Field(description="Absolute base URL clients should target")
    docs_url: str
    openapi_url: str
    streaming: Dict[str, Any] = Field(
        description="SSE endpoint template and supported event names"
    )
    pagination: Dict[str, Any] = Field(
        description="Supported pagination query parameters and their defaults"
    )
    features: Dict[str, bool]
    limits: Dict[str, int]


class ErrorDetail(BaseModel):
    """A single field-level error (validation or business rule)."""

    loc: Optional[List[str]] = None
    msg: str
    type: str = Field(default="error")


class ErrorResponse(BaseModel):
    """Uniform error envelope returned by every failing request.

    ``detail`` is always a string so mobile clients can surface it directly
    without branching on string-vs-list as the raw FastAPI default requires.
    """

    success: bool = False
    detail: str
    code: str = Field(examples=["validation_error"])
    errors: Optional[List[ErrorDetail]] = None
    request_id: Optional[str] = None


class ActionAck(BaseModel):
    """Generic acknowledgement for non-CRUD action endpoints."""

    success: bool = True
    status: str
    message: str


class PaginatedResponse(BaseModel):
    """Envelope describing a page within a larger collection."""

    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    count: int = Field(ge=0, description="Number of items in this page")


class WorkflowExecutionCreated(BaseModel):
    """Minimal reference returned right after an execution is dispatched."""

    id: uuid.UUID
    status: str
    stream_url: str = Field(description="Relative SSE path for this execution")
