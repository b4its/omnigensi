import time
import uuid
from typing import List, Any, Optional
import httpx
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Pagination
from app.core.config import settings
from app.core.database import get_db
from app.core.security import encrypt_api_key, decrypt_api_key
from app.engine.provider_probe import discover_models, probe_chat
from app.models.provider import LLMProvider
from app.models.provider_model import ProviderModel
from app.schemas.provider import (
    ChatTestRequest,
    ChatTestResult,
    DraftChatTestRequest,
    DraftDiscoveryRequest,
    DraftDiscoveryResponse,
    ModelInfo,
    ModelSyncResult,
    ProviderCreate,
    ProviderUpdate,
    ProviderModelResponse,
    ProviderResponse,
    SetDefaultModelRequest,
)

router = APIRouter(prefix="/providers", tags=["LLM Providers"])


class ProviderTestResult(BaseModel):
    """Outcome of actively probing a provider's /models endpoint.

    ``GET /models`` falls back to a canned list when the provider is
    unreachable, so it can never report a bad key. This endpoint always
    reports the truth so clients can show a real health state.
    """

    ok: bool
    status_code: Optional[int] = None
    checked_url: Optional[str] = None
    model_count: int = 0
    latency_ms: int = 0
    error: Optional[str] = None


@router.post("", response_model=ProviderResponse, status_code=status.HTTP_201_CREATED)
async def create_provider(
    payload: ProviderCreate,
    auto_sync_models: bool = False,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Registers a provider.

    Set ``auto_sync_models=true`` to immediately discover and store the
    provider's models so an operator can pick one straight away.
    """
    encrypted_key = encrypt_api_key(payload.api_key)
    provider = LLMProvider(
        name=payload.name,
        provider_type=payload.provider_type,
        base_url=payload.base_url.rstrip("/"),
        api_key_encrypted=encrypted_key,
        default_headers=payload.default_headers,
        is_active=payload.is_active,
        default_model=payload.default_model,
    )
    db.add(provider)
    await db.commit()
    await db.refresh(provider)

    if auto_sync_models:
        await _sync_provider_models(db, provider)
        # The sync commits internally, which expires `provider`; re-load it so
        # the response reflects the auto-selected default model.
        await db.refresh(provider)
    return ProviderResponse(
        id=provider.id,
        name=provider.name,
        provider_type=provider.provider_type,
        base_url=provider.base_url,
        default_headers=provider.default_headers,
        is_active=provider.is_active,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
        has_api_key=bool(payload.api_key),
        default_model=provider.default_model,
    )


@router.get("", response_model=List[ProviderResponse])
async def list_providers(
    response: Response,
    page: Pagination = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Any:
    total = await db.scalar(select(func.count()).select_from(LLMProvider)) or 0
    result = await db.execute(
        select(LLMProvider)
        .order_by(LLMProvider.created_at.desc())
        .limit(page.limit)
        .offset(page.offset)
    )
    providers = result.scalars().all()
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Limit"] = str(page.limit)
    response.headers["X-Offset"] = str(page.offset)
    return [
        ProviderResponse(
            id=p.id,
            name=p.name,
            provider_type=p.provider_type,
            base_url=p.base_url,
            default_headers=p.default_headers,
            is_active=p.is_active,
            created_at=p.created_at,
            updated_at=p.updated_at,
            has_api_key=bool(p.api_key_encrypted),
            default_model=p.default_model,
        )
        for p in providers
    ]


@router.post("/discover-draft", response_model=DraftDiscoveryResponse)
async def discover_draft_models(payload: DraftDiscoveryRequest) -> Any:
    """List models for credentials that have not been saved yet.

    Lets the registration form validate and show a model picker before the
    provider exists, so a bad key is caught at entry rather than on first use.
    """
    result = await discover_models(
        payload.base_url, payload.api_key, None
    )
    return DraftDiscoveryResponse(
        ok=result.ok,
        models=[
            ModelInfo(
                id=m["model_id"],
                name=m.get("display_name"),
                context_length=m.get("context_length"),
                description=m.get("description"),
                pricing=m.get("pricing") or None,
            )
            for m in result.models
        ],
        checked_url=result.checked_url,
        latency_ms=result.latency_ms,
        error=result.error,
    )


@router.post("/chat-test-draft", response_model=ChatTestResult)
async def chat_test_draft(payload: DraftChatTestRequest) -> Any:
    """Real completion using unsaved credentials and a chosen model."""
    probe = await probe_chat(
        base_url=payload.base_url,
        api_key=payload.api_key,
        model_id=payload.model_id,
        prompt=payload.prompt,
        provider_type=payload.provider_type,
    )
    return ChatTestResult(
        ok=probe.ok,
        model_id=probe.model_id,
        response_text=probe.response_text,
        latency_ms=probe.latency_ms,
        status_code=probe.status_code,
        prompt_tokens=probe.prompt_tokens,
        completion_tokens=probe.completion_tokens,
        checked_url=probe.checked_url,
        error=probe.error,
    )


@router.get("/{provider_id}", response_model=ProviderResponse)
async def get_provider(
    provider_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> Any:
    provider = await db.get(LLMProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return ProviderResponse(
        id=provider.id,
        name=provider.name,
        provider_type=provider.provider_type,
        base_url=provider.base_url,
        default_headers=provider.default_headers,
        is_active=provider.is_active,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
        has_api_key=bool(provider.api_key_encrypted),
        default_model=provider.default_model,
    )


@router.put("/{provider_id}", response_model=ProviderResponse)
async def update_provider(
    provider_id: uuid.UUID,
    payload: ProviderUpdate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    provider = await db.get(LLMProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    if payload.name is not None:
        provider.name = payload.name
    if payload.provider_type is not None:
        provider.provider_type = payload.provider_type
    if payload.base_url is not None:
        provider.base_url = payload.base_url.rstrip("/")
    if payload.api_key is not None:
        provider.api_key_encrypted = encrypt_api_key(payload.api_key)
    if payload.default_headers is not None:
        provider.default_headers = payload.default_headers
    if payload.is_active is not None:
        provider.is_active = payload.is_active
    if payload.default_model is not None:
        provider.default_model = payload.default_model

    await db.commit()
    await db.refresh(provider)
    return ProviderResponse(
        id=provider.id,
        name=provider.name,
        provider_type=provider.provider_type,
        base_url=provider.base_url,
        default_headers=provider.default_headers,
        is_active=provider.is_active,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
        has_api_key=bool(provider.api_key_encrypted),
        default_model=provider.default_model,
    )


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(
    provider_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> None:
    provider = await db.get(LLMProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    await db.delete(provider)
    await db.commit()


@router.get("/{provider_id}/models", response_model=List[ModelInfo])
async def fetch_provider_models(
    provider_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> Any:
    """Live model discovery.

    When the provider cannot be reached this returns the models stored by the
    last successful sync instead of inventing a canned list, so the picker
    keeps working without ever pretending a dead key succeeded.
    """
    provider = await db.get(LLMProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    discovery = await discover_models(
        provider.base_url,
        decrypt_api_key(provider.api_key_encrypted),
        provider.default_headers,
    )
    if discovery.ok:
        return [
            ModelInfo(
                id=m["model_id"],
                name=m.get("display_name"),
                context_length=m.get("context_length"),
                description=m.get("description"),
                pricing=m.get("pricing") or None,
            )
            for m in discovery.models
        ]

    stored = await _stored_models(db, provider_id)
    return [
        ModelInfo(
            id=m.model_id,
            name=m.display_name,
            context_length=m.context_length,
            description=m.description,
            pricing=m.pricing or None,
        )
        for m in stored
    ]


async def _stored_models(db: AsyncSession, provider_id: uuid.UUID) -> List[ProviderModel]:
    result = await db.execute(
        select(ProviderModel)
        .where(ProviderModel.provider_id == provider_id)
        .order_by(ProviderModel.is_default.desc(), ProviderModel.model_id.asc())
    )
    return list(result.scalars().all())


async def _sync_provider_models(
    db: AsyncSession, provider: LLMProvider
) -> ModelSyncResult:
    """Upsert the provider's models and flag the ones that disappeared.

    Rows are never deleted: an agent may already reference a model, and a
    transient outage should not destroy the operator's selection.
    """
    discovery = await discover_models(
        provider.base_url,
        decrypt_api_key(provider.api_key_encrypted),
        provider.default_headers,
    )
    if not discovery.ok:
        return ModelSyncResult(
            ok=False,
            provider_id=provider.id,
            discovered=0,
            added=0,
            updated=0,
            marked_unavailable=0,
            total_stored=len(await _stored_models(db, provider.id)),
            checked_url=discovery.checked_url,
            latency_ms=discovery.latency_ms,
            error=discovery.error,
        )

    existing = {m.model_id: m for m in await _stored_models(db, provider.id)}
    seen: set[str] = set()
    added = updated = 0

    for entry in discovery.models:
        model_id = entry["model_id"]
        seen.add(model_id)
        row = existing.get(model_id)
        if row is None:
            db.add(
                ProviderModel(
                    provider_id=provider.id,
                    model_id=model_id,
                    display_name=entry.get("display_name"),
                    context_length=entry.get("context_length"),
                    description=entry.get("description"),
                    pricing=entry.get("pricing") or {},
                    is_available=True,
                )
            )
            added += 1
        else:
            row.display_name = entry.get("display_name") or row.display_name
            row.context_length = entry.get("context_length") or row.context_length
            row.description = entry.get("description") or row.description
            row.pricing = entry.get("pricing") or row.pricing
            row.is_available = True
            updated += 1

    marked = 0
    for model_id, row in existing.items():
        if model_id not in seen and row.is_available:
            row.is_available = False
            marked += 1

    await db.commit()

    stored = await _stored_models(db, provider.id)
    # Adopt a default automatically so the picker is never empty.
    if not any(m.is_default for m in stored) and stored:
        available = [m for m in stored if m.is_available]
        pick = available[0] if available else stored[0]
        pick.is_default = True
        provider.default_model = pick.model_id
        await db.commit()
        stored = await _stored_models(db, provider.id)

    return ModelSyncResult(
        ok=True,
        provider_id=provider.id,
        discovered=len(discovery.models),
        added=added,
        updated=updated,
        marked_unavailable=marked,
        total_stored=len(stored),
        checked_url=discovery.checked_url,
        latency_ms=discovery.latency_ms,
    )


@router.get("/{provider_id}/model-registry", response_model=List[ProviderModelResponse])
async def list_provider_models(
    provider_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> Any:
    """Models previously stored for this provider (no live call)."""
    provider = await db.get(LLMProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return await _stored_models(db, provider_id)


@router.post("/{provider_id}/models/sync", response_model=ModelSyncResult)
async def sync_provider_models(
    provider_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> Any:
    """Auto-add every model the provider reports, keeping existing rows."""
    provider = await db.get(LLMProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return await _sync_provider_models(db, provider)


@router.put(
    "/{provider_id}/default-model", response_model=ProviderModelResponse
)
async def set_default_model(
    provider_id: uuid.UUID,
    payload: SetDefaultModelRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Selects which stored model this provider should use by default."""
    provider = await db.get(LLMProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    stored = await _stored_models(db, provider_id)
    target = next((m for m in stored if m.model_id == payload.model_id), None)
    if target is None:
        raise HTTPException(
            status_code=404,
            detail=f"Model '{payload.model_id}' is not registered for this provider. Run a model sync first.",
        )

    for row in stored:
        row.is_default = row.model_id == payload.model_id
    provider.default_model = payload.model_id
    await db.commit()
    await db.refresh(target)
    return target


@router.post("/{provider_id}/chat-test", response_model=ChatTestResult)
async def chat_test_provider(
    provider_id: uuid.UUID,
    payload: ChatTestRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Runs a real completion so the operator can see an actual response.

    Unlike ``/test`` (which only lists models) this proves the key, the
    selected model and the routing all work, and returns the reply text.
    """
    provider = await db.get(LLMProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    model_id = payload.model_id or provider.default_model
    if not model_id:
        raise HTTPException(
            status_code=400,
            detail="No model selected. Sync models and choose a default first.",
        )

    probe = await probe_chat(
        base_url=provider.base_url,
        api_key=decrypt_api_key(provider.api_key_encrypted),
        model_id=model_id,
        prompt=payload.prompt,
        provider_type=provider.provider_type,
        default_headers=provider.default_headers,
        max_tokens=payload.max_tokens,
    )

    return ChatTestResult(
        ok=probe.ok,
        model_id=probe.model_id,
        response_text=probe.response_text,
        latency_ms=probe.latency_ms,
        status_code=probe.status_code,
        prompt_tokens=probe.prompt_tokens,
        completion_tokens=probe.completion_tokens,
        checked_url=probe.checked_url,
        error=probe.error,
    )


@router.post("/{provider_id}/test", response_model=ProviderTestResult)
async def test_provider_connection(
    provider_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> Any:
    """Actively probe the provider to verify credentials and reachability.

    Unlike ``GET /{id}/models`` this never substitutes fallback data: a wrong
    key or an unreachable host reports ``ok: false`` with the real status.
    """
    provider = await db.get(LLMProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    raw_key = decrypt_api_key(provider.api_key_encrypted)
    headers = {"Authorization": f"Bearer {raw_key}"} if raw_key else {}
    if provider.default_headers:
        headers.update({str(k): str(v) for k, v in provider.default_headers.items()})

    base_url = provider.base_url.rstrip("/")
    candidates = []
    if base_url.endswith("/v1") or base_url.endswith("/api/v1"):
        candidates.append(f"{base_url}/models")
    else:
        candidates.extend(
            [
                f"{base_url}/v1/models",
                f"{base_url}/models",
                f"{base_url}/api/tags",
            ]
        )

    started = time.perf_counter()
    last_error = "No candidate endpoint responded"
    last_status: Optional[int] = None
    last_url: Optional[str] = None

    async with httpx.AsyncClient(
        timeout=settings.PROVIDER_TIMEOUT_SECONDS,
        verify=settings.PROVIDER_TLS_VERIFY,
    ) as client:
        for url in candidates:
            try:
                resp = await client.get(url, headers=headers)
                last_url, last_status = url, resp.status_code
                if resp.status_code == 200:
                    payload = resp.json()

                    def _count(block: Any) -> int:
                        return len(block) if isinstance(block, list) else 0

                    model_count = 0
                    if isinstance(payload, dict):
                        model_count = _count(payload.get("data")) or _count(
                            payload.get("models")
                        )
                    return ProviderTestResult(
                        ok=True,
                        status_code=resp.status_code,
                        checked_url=url,
                        model_count=model_count,
                        latency_ms=int((time.perf_counter() - started) * 1000),
                    )
                if resp.status_code in (401, 403):
                    return ProviderTestResult(
                        ok=False,
                        status_code=resp.status_code,
                        checked_url=url,
                        latency_ms=int((time.perf_counter() - started) * 1000),
                        error="Authentication failed - check the API key",
                    )
                last_error = f"Provider responded with HTTP {resp.status_code}"
            except httpx.TimeoutException:
                last_error = "Connection timed out"
            except Exception as exc:  # noqa: BLE001 - surfaced to the client
                last_error = str(exc)

    return ProviderTestResult(
        ok=False,
        status_code=last_status,
        checked_url=last_url,
        latency_ms=int((time.perf_counter() - started) * 1000),
        error=last_error,
    )
