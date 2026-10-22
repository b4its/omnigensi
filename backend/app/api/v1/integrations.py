"""External project integrations router.

Provides:
1. Operator registry & real-time monitoring deck for external projects/targets
   (e.g. Laravel project "agen xishie" at http://localhost:8208/).
2. Modular API endpoints for registered external clients to authenticate via
   API key and consume AI models/workflows from Omnigensi.
"""

import asyncio
import json
import logging
import secrets
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.engine.llm_factory import create_llm_client
from app.models.integration_client import IntegrationClient
from app.models.provider import LLMProvider
from app.models.provider_model import ProviderModel
from app.schemas.integration import (
    ExternalChatChoice,
    ExternalChatMessage,
    ExternalChatRequest,
    ExternalChatResponse,
    ExternalHandshakeResponse,
    IntegrationClientCreate,
    IntegrationClientResponse,
    IntegrationClientUpdate,
    IntegrationProbeResult,
)

logger = logging.getLogger("omnigensi.integrations")

router = APIRouter(prefix="/integrations", tags=["Integrations & Connected Projects"])


def generate_api_key() -> str:
    """Generate a cryptographically secure integration client API key."""
    return f"omni_live_{secrets.token_urlsafe(24)}"


async def probe_client_connectivity(client: IntegrationClient) -> IntegrationProbeResult:
    """Probe outbound connectivity to an external project target URL."""
    base = client.target_url.rstrip("/")
    endpoint = client.health_endpoint.strip()
    path = endpoint if endpoint.startswith("/") else f"/{endpoint}"
    full_url = f"{base}{path}"

    t0 = time.perf_counter()
    headers_subset: Dict[str, str] = {}
    try:
        async with httpx.AsyncClient(timeout=6.0, follow_redirects=True, verify=False) as http:
            res = await http.get(full_url)
            latency_ms = int((time.perf_counter() - t0) * 1000)

            server = res.headers.get("server")
            php = res.headers.get("x-powered-by")
            server_header = f"{server} ({php})" if server and php else (server or php or "HTTP Service")

            for k, v in res.headers.items():
                if k.lower() in ("server", "content-type", "x-powered-by", "set-cookie", "date"):
                    headers_subset[k] = v

            # 2xx / 3xx is reachable and healthy
            is_ok = 200 <= res.status_code < 400
            status_str = "online" if is_ok else "degraded"
            err = None if is_ok else f"Target returned HTTP status {res.status_code}"

            return IntegrationProbeResult(
                client_id=client.id,
                name=client.name,
                target_url=client.target_url,
                full_url=full_url,
                status=status_str,
                status_code=res.status_code,
                latency_ms=latency_ms,
                server_header=server_header,
                error=err,
                headers=headers_subset,
                checked_at=datetime.now(timezone.utc),
            )
    except Exception as exc:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        err_type = type(exc).__name__
        err_msg = str(exc) or err_type
        if "ConnectError" in err_type or "Connection refused" in err_msg:
            err_msg = "Connection refused (target process not running or port unreachable)"
        elif "Timeout" in err_type:
            err_msg = "Connection timed out (> 6.0s)"

        return IntegrationProbeResult(
            client_id=client.id,
            name=client.name,
            target_url=client.target_url,
            full_url=full_url,
            status="offline",
            status_code=None,
            latency_ms=latency_ms,
            server_header=None,
            error=err_msg,
            headers={},
            checked_at=datetime.now(timezone.utc),
        )


async def ensure_default_xishie_client(db: AsyncSession) -> IntegrationClient:
    """Pre-seeds the Laravel 'agen xishie' integration if no clients exist."""
    client = IntegrationClient(
        name="agen xishie",
        description="Laravel Agency Target Project (agen xishie)",
        target_url="http://localhost:8208/",
        health_endpoint="/",
        api_key=generate_api_key(),
        is_active=True,
        allowed_models=["*"],
        allowed_workflows=["*"],
        allowed_endpoints=["*"],
        status="unknown",
    )
    db.add(client)
    await db.commit()
    await db.refresh(client)

    # Perform initial probe in background/inline so initial status is populated
    try:
        probe = await probe_client_connectivity(client)
        client.status = probe.status
        client.last_status_code = probe.status_code
        client.last_latency_ms = probe.latency_ms
        client.last_checked_at = probe.checked_at
        client.last_error = probe.error
        client.target_server = probe.server_header
        client.extra_metadata = {"headers": probe.headers}
        await db.commit()
        await db.refresh(client)
    except Exception as e:
        logger.warning("Initial probe for agen xishie encountered: %s", e)

    return client


# -----------------------------------------------------------------------------
# Operator Management Endpoints (requires operator session)
# -----------------------------------------------------------------------------

@router.get("/clients", response_model=List[IntegrationClientResponse])
async def list_integration_clients(
    db: AsyncSession = Depends(get_db),
) -> List[IntegrationClientResponse]:
    """List all registered external integration clients.

    If the database has no registered clients yet, automatically pre-seeds
    the user's Laravel project 'agen xishie' (http://localhost:8208/).
    """
    clients = (
        (
            await db.execute(
                select(IntegrationClient).order_by(desc(IntegrationClient.created_at))
            )
        )
        .scalars()
        .all()
    )

    if not clients:
        xishie = await ensure_default_xishie_client(db)
        return [IntegrationClientResponse.model_validate(xishie)]

    return [IntegrationClientResponse.model_validate(c) for c in clients]


@router.post("/clients", response_model=IntegrationClientResponse, status_code=status.HTTP_201_CREATED)
async def register_integration_client(
    payload: IntegrationClientCreate,
    probe_immediately: bool = True,
    db: AsyncSession = Depends(get_db),
) -> IntegrationClientResponse:
    """Register a new external project or client app.

    Generates a unique client API key and performs an immediate connectivity check.
    """
    target = payload.target_url.strip()
    if not (target.startswith("http://") or target.startswith("https://")):
        raise HTTPException(
            status_code=422,
            detail="Target URL must start with http:// or https://",
        )

    # Prevent duplicate project names
    existing = await db.scalar(
        select(IntegrationClient.id).where(IntegrationClient.name == payload.name.strip())
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"An integration client named '{payload.name.strip()}' already exists.",
        )

    client = IntegrationClient(
        name=payload.name.strip(),
        description=payload.description.strip() if payload.description else None,
        target_url=target,
        health_endpoint=payload.health_endpoint.strip() or "/",
        api_key=generate_api_key(),
        is_active=payload.is_active,
        allowed_models=payload.allowed_models,
        allowed_workflows=payload.allowed_workflows,
        allowed_endpoints=payload.allowed_endpoints,
        status="unknown",
    )
    db.add(client)
    await db.commit()
    await db.refresh(client)

    if probe_immediately:
        try:
            probe = await probe_client_connectivity(client)
            client.status = probe.status
            client.last_status_code = probe.status_code
            client.last_latency_ms = probe.latency_ms
            client.last_checked_at = probe.checked_at
            client.last_error = probe.error
            client.target_server = probe.server_header
            client.extra_metadata = {"headers": probe.headers}
            await db.commit()
            await db.refresh(client)
        except Exception as exc:
            logger.warning("Probe immediately failed for %s: %s", client.name, exc)

    return IntegrationClientResponse.model_validate(client)


@router.get("/clients/{client_id}", response_model=IntegrationClientResponse)
async def get_integration_client(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> IntegrationClientResponse:
    client = await db.get(IntegrationClient, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Integration client not found")
    return IntegrationClientResponse.model_validate(client)


@router.put("/clients/{client_id}", response_model=IntegrationClientResponse)
async def update_integration_client(
    client_id: uuid.UUID,
    payload: IntegrationClientUpdate,
    db: AsyncSession = Depends(get_db),
) -> IntegrationClientResponse:
    client = await db.get(IntegrationClient, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Integration client not found")

    if payload.name is not None and payload.name.strip() != client.name:
        dup = await db.scalar(
            select(IntegrationClient.id).where(
                IntegrationClient.name == payload.name.strip(),
                IntegrationClient.id != client.id,
            )
        )
        if dup:
            raise HTTPException(
                status_code=409,
                detail=f"An integration client named '{payload.name.strip()}' already exists.",
            )
        client.name = payload.name.strip()

    if payload.description is not None:
        client.description = payload.description.strip() if payload.description else None

    if payload.target_url is not None:
        t = payload.target_url.strip()
        if not (t.startswith("http://") or t.startswith("https://")):
            raise HTTPException(
                status_code=422,
                detail="Target URL must start with http:// or https://",
            )
        client.target_url = t

    if payload.health_endpoint is not None:
        client.health_endpoint = payload.health_endpoint.strip() or "/"

    if payload.is_active is not None:
        client.is_active = payload.is_active

    if payload.allowed_models is not None:
        client.allowed_models = payload.allowed_models

    if payload.allowed_workflows is not None:
        client.allowed_workflows = payload.allowed_workflows

    if payload.allowed_endpoints is not None:
        client.allowed_endpoints = payload.allowed_endpoints

    await db.commit()
    await db.refresh(client)
    return IntegrationClientResponse.model_validate(client)


@router.delete("/clients/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_integration_client(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    client = await db.get(IntegrationClient, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Integration client not found")
    await db.delete(client)
    await db.commit()


@router.post("/clients/{client_id}/regenerate-key", response_model=IntegrationClientResponse)
async def regenerate_client_api_key(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> IntegrationClientResponse:
    """Rotate the client's API key. Previous key is immediately invalidated."""
    client = await db.get(IntegrationClient, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Integration client not found")

    client.api_key = generate_api_key()
    await db.commit()
    await db.refresh(client)
    return IntegrationClientResponse.model_validate(client)


@router.post("/clients/{client_id}/ping", response_model=IntegrationProbeResult)
async def ping_client_target(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> IntegrationProbeResult:
    """Probe an individual client target URL right now and persist the result."""
    client = await db.get(IntegrationClient, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Integration client not found")

    probe = await probe_client_connectivity(client)

    client.status = probe.status
    client.last_status_code = probe.status_code
    client.last_latency_ms = probe.latency_ms
    client.last_checked_at = probe.checked_at
    client.last_error = probe.error
    client.target_server = probe.server_header
    client.extra_metadata = {"headers": probe.headers}
    await db.commit()

    return probe


@router.post("/ping-all", response_model=List[IntegrationProbeResult])
async def ping_all_targets(
    db: AsyncSession = Depends(get_db),
) -> List[IntegrationProbeResult]:
    """Concurrent connectivity check across all registered targets."""
    clients = (
        (
            await db.execute(
                select(IntegrationClient).where(IntegrationClient.is_active.is_(True))
            )
        )
        .scalars()
        .all()
    )

    if not clients:
        return []

    results = await asyncio.gather(
        *(probe_client_connectivity(c) for c in clients),
        return_exceptions=False,
    )

    for client, probe in zip(clients, results):
        client.status = probe.status
        client.last_status_code = probe.status_code
        client.last_latency_ms = probe.latency_ms
        client.last_checked_at = probe.checked_at
        client.last_error = probe.error
        client.target_server = probe.server_header
        client.extra_metadata = {"headers": probe.headers}

    await db.commit()
    return results


@router.post("/seed-xishie", response_model=IntegrationClientResponse)
async def seed_agen_xishie(
    db: AsyncSession = Depends(get_db),
) -> IntegrationClientResponse:
    """Quick-seed or reset Laravel 'agen xishie' (http://localhost:8208/)."""
    existing = await db.scalar(
        select(IntegrationClient).where(IntegrationClient.name == "agen xishie")
    )
    if existing:
        probe = await probe_client_connectivity(existing)
        existing.status = probe.status
        existing.last_status_code = probe.status_code
        existing.last_latency_ms = probe.latency_ms
        existing.last_checked_at = probe.checked_at
        existing.last_error = probe.error
        existing.target_server = probe.server_header
        await db.commit()
        await db.refresh(existing)
        return IntegrationClientResponse.model_validate(existing)

    client = await ensure_default_xishie_client(db)
    return IntegrationClientResponse.model_validate(client)


# -----------------------------------------------------------------------------
# External Client Inbound Endpoints (for Laravel, curl, other projects)
# Authenticated via X-API-Key or Bearer token issued to the integration client.
# -----------------------------------------------------------------------------

async def get_external_client(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> IntegrationClient:
    """Extract and authenticate an external project API key."""
    candidate_key: Optional[str] = None
    if x_api_key and x_api_key.strip():
        candidate_key = x_api_key.strip()
    elif authorization and authorization.lower().startswith("bearer "):
        candidate_key = authorization[7:].strip()

    if not candidate_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing integration API Key. Provide 'X-API-Key' or 'Authorization: Bearer <key>'.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    client = await db.scalar(
        select(IntegrationClient).where(
            IntegrationClient.api_key == candidate_key,
            IntegrationClient.is_active.is_(True),
        )
    )
    if not client:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, revoked, or inactive integration API Key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Record inbound request timestamp and counter
    client.last_handshake_at = datetime.now(timezone.utc)
    client.inbound_requests_count = (client.inbound_requests_count or 0) + 1
    await db.commit()

    return client


@router.get("/v1/handshake", response_model=ExternalHandshakeResponse)
async def external_handshake(
    client: IntegrationClient = Depends(get_external_client),
    db: AsyncSession = Depends(get_db),
) -> ExternalHandshakeResponse:
    """Inbound handshake verification endpoint for external projects (Laravel).

    External project calls this to verify its API key and discover available
    models and system version.
    """
    providers = (
        (
            await db.execute(
                select(LLMProvider)
                .where(LLMProvider.is_active.is_(True))
                .order_by(LLMProvider.name.asc())
            )
        )
        .scalars()
        .all()
    )

    models_list = []
    for p in providers:
        p_models = (
            (
                await db.execute(
                    select(ProviderModel).where(
                        ProviderModel.provider_id == p.id,
                        ProviderModel.is_available.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        for m in p_models:
            models_list.append(
                {
                    "provider": p.name,
                    "model_id": m.model_id,
                    "display_name": m.display_name,
                    "is_default": m.is_default,
                }
            )
        if not p_models and p.default_model:
            models_list.append(
                {
                    "provider": p.name,
                    "model_id": p.default_model,
                    "display_name": p.default_model,
                    "is_default": True,
                }
            )

    return ExternalHandshakeResponse(
        status="connected",
        client_id=client.id,
        client_name=client.name,
        target_url=client.target_url,
        omnigensi_version=settings.APP_VERSION,
        allowed_models=client.allowed_models or ["*"],
        available_models=models_list,
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/v1/models")
async def external_list_models(
    client: IntegrationClient = Depends(get_external_client),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Returns models available to this registered client."""
    providers = (
        (
            await db.execute(
                select(LLMProvider)
                .where(LLMProvider.is_active.is_(True))
                .order_by(LLMProvider.name.asc())
            )
        )
        .scalars()
        .all()
    )

    allowed = set(client.allowed_models or ["*"])
    allow_all = "*" in allowed

    items = []
    for p in providers:
        p_models = (
            (
                await db.execute(
                    select(ProviderModel).where(
                        ProviderModel.provider_id == p.id,
                        ProviderModel.is_available.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        for m in p_models:
            if allow_all or m.model_id in allowed:
                items.append(
                    {
                        "id": m.model_id,
                        "display_name": m.display_name,
                        "provider": p.name,
                        "provider_id": str(p.id),
                        "context_length": m.context_length,
                        "is_default": m.is_default,
                    }
                )
        if not p_models and p.default_model and (allow_all or p.default_model in allowed):
            items.append(
                {
                    "id": p.default_model,
                    "display_name": p.default_model,
                    "provider": p.name,
                    "provider_id": str(p.id),
                    "context_length": None,
                    "is_default": True,
                }
            )

    return {"object": "list", "data": items}


@router.post("/v1/chat/completions")
async def external_chat_completion(
    payload: ExternalChatRequest,
    client: IntegrationClient = Depends(get_external_client),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """OpenAI-compatible chat completion endpoint for external clients (Laravel).

    Supports both standard non-streaming JSON (stream=false) and Server-Sent Events (stream=true).
    """
    # 1. Resolve Provider
    provider: Optional[LLMProvider] = None
    if payload.provider_id:
        provider = await db.get(LLMProvider, payload.provider_id)
        if not provider or not provider.is_active:
            raise HTTPException(status_code=400, detail="Requested provider is unavailable.")
    else:
        # Pick the first active provider
        provider = await db.scalar(
            select(LLMProvider)
            .where(LLMProvider.is_active.is_(True))
            .order_by(LLMProvider.name.asc())
        )
        if not provider:
            raise HTTPException(
                status_code=503,
                detail="No active LLM providers configured in Omnigensi vault.",
            )

    # 2. Resolve Model
    chosen_model = payload.model or provider.default_model
    if not chosen_model:
        # Try finding any model registered for this provider
        first_model = await db.scalar(
            select(ProviderModel.model_id).where(
                ProviderModel.provider_id == provider.id,
                ProviderModel.is_available.is_(True),
            )
        )
        chosen_model = first_model or "default"

    # 3. Check client model permissions
    allowed = set(client.allowed_models or ["*"])
    if "*" not in allowed and chosen_model not in allowed:
        raise HTTPException(
            status_code=403,
            detail=f"Client '{client.name}' is not authorized to use model '{chosen_model}'.",
        )

    messages = [m.model_dump() for m in payload.messages]

    # Non-streaming JSON completion (ideal for Laravel Http::post)
    if not payload.stream:
        started = time.perf_counter()
        try:
            llm = create_llm_client(
                provider,
                chosen_model,
                temperature=payload.temperature,
                max_tokens=payload.max_tokens,
                streaming=False,
            )
            response = await llm.ainvoke(messages)
            content = response.content if isinstance(response.content, str) else str(response.content)
            latency_ms = int((time.perf_counter() - started) * 1000)

            return ExternalChatResponse(
                id=f"chatcmpl-{uuid.uuid4().hex[:12]}",
                object="chat.completion",
                model=chosen_model,
                client=client.name,
                choices=[
                    ExternalChatChoice(
                        index=0,
                        message=ExternalChatMessage(role="assistant", content=content),
                        finish_reason="stop",
                    )
                ],
                latency_ms=latency_ms,
            )
        except Exception as exc:
            logger.error("External chat completion failed: %s", exc)
            raise HTTPException(
                status_code=502,
                detail=f"Upstream provider error: {str(exc)}",
            )

    # Streaming SSE response
    def _sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"

    async def event_stream():
        started = time.perf_counter()
        yield _sse("start", {"model": chosen_model, "client": client.name})
        collected = []
        try:
            llm = create_llm_client(
                provider,
                chosen_model,
                temperature=payload.temperature,
                max_tokens=payload.max_tokens,
                streaming=True,
            )
            async for chunk in llm.astream(messages):
                text = chunk.content if isinstance(chunk.content, str) else ""
                if text:
                    collected.append(text)
                    yield _sse("token", {"text": text})

            final = "".join(collected)
            yield _sse(
                "done",
                {
                    "content": final,
                    "latency_ms": int((time.perf_counter() - started) * 1000),
                },
            )
        except Exception as exc:
            yield _sse("error", {"message": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
