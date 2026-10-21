import uuid
from typing import List, Any
import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import encrypt_api_key, decrypt_api_key
from app.models.provider import LLMProvider
from app.schemas.provider import (
    ProviderCreate,
    ProviderUpdate,
    ProviderResponse,
    ModelInfo,
)

router = APIRouter(prefix="/providers", tags=["LLM Providers"])


@router.post("", response_model=ProviderResponse, status_code=status.HTTP_201_CREATED)
async def create_provider(
    payload: ProviderCreate, db: AsyncSession = Depends(get_db)
) -> Any:
    encrypted_key = encrypt_api_key(payload.api_key)
    provider = LLMProvider(
        name=payload.name,
        provider_type=payload.provider_type,
        base_url=payload.base_url.rstrip("/"),
        api_key_encrypted=encrypted_key,
        default_headers=payload.default_headers,
        is_active=payload.is_active,
    )
    db.add(provider)
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
        has_api_key=bool(payload.api_key),
    )


@router.get("", response_model=List[ProviderResponse])
async def list_providers(db: AsyncSession = Depends(get_db)) -> Any:
    result = await db.execute(
        select(LLMProvider).order_by(LLMProvider.created_at.desc())
    )
    providers = result.scalars().all()
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
        )
        for p in providers
    ]


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
        candidates.append(f"{base_url}/v1/models")
        candidates.append(f"{base_url}/models")
        candidates.append(f"{base_url}/api/tags")  # Ollama native

    models: List[ModelInfo] = []
    last_error = ""

    async with httpx.AsyncClient(timeout=15.0, verify=False) as client:
        for url in candidates:
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    # Standard OpenAI format: {"data": [{"id": "...", ...}]}
                    if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
                        for m in data["data"]:
                            m_id = m.get("id") or m.get("name", "unknown")
                            models.append(
                                ModelInfo(
                                    id=m_id,
                                    name=m.get("name", m_id),
                                    context_length=m.get("context_length"),
                                    description=m.get("description"),
                                    pricing=m.get("pricing"),
                                )
                            )
                        break
                    # Ollama format: {"models": [{"name": "...", "model": "..."}]}
                    elif isinstance(data, dict) and "models" in data and isinstance(data["models"], list):
                        for m in data["models"]:
                            m_name = m.get("model") or m.get("name", "unknown")
                            models.append(
                                ModelInfo(
                                    id=m_name,
                                    name=m_name,
                                    description=f"Format: {m.get('details', {}).get('format', 'ollama')}",
                                )
                            )
                        break
            except Exception as e:
                last_error = str(e)

    # If provider failed to return models or local mock fallback
    if not models:
        # Provide common fallback models based on provider_type
        if provider.provider_type.lower() == "openrouter":
            models = [
                ModelInfo(id="meta-llama/llama-3.3-70b-instruct", name="Llama 3.3 70B Instruct"),
                ModelInfo(id="anthropic/claude-3.5-sonnet", name="Claude 3.5 Sonnet"),
                ModelInfo(id="openai/gpt-4o", name="GPT-4o"),
                ModelInfo(id="google/gemini-2.0-flash-exp:free", name="Gemini 2.0 Flash (Free)"),
                ModelInfo(id="deepseek/deepseek-chat", name="DeepSeek V3"),
            ]
        elif provider.provider_type.lower() == "openai":
            models = [
                ModelInfo(id="gpt-4o", name="GPT-4o"),
                ModelInfo(id="gpt-4o-mini", name="GPT-4o Mini"),
                ModelInfo(id="o1-preview", name="o1 Preview"),
            ]
        elif provider.provider_type.lower() == "ollama":
            models = [
                ModelInfo(id="llama3.2:latest", name="Llama 3.2 (Local)"),
                ModelInfo(id="qwen2.5-coder:7b", name="Qwen 2.5 Coder 7B (Local)"),
                ModelInfo(id="deepseek-r1:8b", name="DeepSeek R1 8B (Local)"),
            ]
        else:
            models = [
                ModelInfo(id="default-model", name="Default Model (Check Connection)"),
            ]

    return models
