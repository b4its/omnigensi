"""Interactive AI chat console.

Two endpoints, deliberately kept small:

* ``GET /chat/models`` - every model the operator can talk to, flattened from
  the provider registry that model sync populates. Providers without synced
  models fall back to their single ``default_model`` so a freshly configured
  provider is still usable before a sync.
* ``POST /chat/completions`` - streams one assistant reply over SSE. The model
  and provider are chosen per request, so the UI can switch mid-conversation.

Streaming is used rather than a single JSON body so long answers appear as
they are generated instead of after a long silent wait.
"""

import json
import time
import uuid
from typing import AsyncGenerator, List

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.engine.llm_factory import create_llm_client
from app.models.provider import LLMProvider
from app.models.provider_model import ProviderModel
from app.schemas.chat import (
    ChatCompletionRequest,
    ChatModelOption,
    ChatModelsResponse,
)

router = APIRouter(prefix="/chat", tags=["AI Chat"])


async def _resolve_provider(db: AsyncSession, provider_id: uuid.UUID) -> LLMProvider:
    provider = await db.get(LLMProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    if not provider.is_active:
        raise HTTPException(
            status_code=409, detail="Provider is inactive; activate it first"
        )
    return provider


@router.get("/models", response_model=ChatModelsResponse)
async def list_chat_models(db: AsyncSession = Depends(get_db)) -> ChatModelsResponse:
    """Every selectable model across active providers.

    Models come from the synced registry. A provider that has not been synced
    yet still contributes its ``default_model`` (if set) so it is never
    invisible in the picker.
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

    options: List[ChatModelOption] = []
    for provider in providers:
        rows = (
            (
                await db.execute(
                    select(ProviderModel)
                    .where(
                        ProviderModel.provider_id == provider.id,
                        ProviderModel.is_available.is_(True),
                    )
                    .order_by(
                        ProviderModel.is_default.desc(),
                        ProviderModel.model_id.asc(),
                    )
                )
            )
            .scalars()
            .all()
        )
        if rows:
            for row in rows:
                options.append(
                    ChatModelOption(
                        provider_id=provider.id,
                        provider_name=provider.name,
                        model_id=row.model_id,
                        display_name=row.display_name,
                        context_length=row.context_length,
                        is_default=row.is_default,
                        is_available=row.is_available,
                    )
                )
        elif provider.default_model:
            options.append(
                ChatModelOption(
                    provider_id=provider.id,
                    provider_name=provider.name,
                    model_id=provider.default_model,
                    display_name=provider.default_model,
                    is_default=True,
                )
            )

    return ChatModelsResponse(models=options)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@router.post("/completions")
async def chat_completion(
    payload: ChatCompletionRequest,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Stream a single assistant reply as Server-Sent Events.

    Events: ``start`` (echoes provider/model), ``token`` (incremental text),
    ``done`` (final text + usage), ``error`` (message). The client keeps the
    last ``token`` sequence so it can render progressively.
    """
    provider = await _resolve_provider(db, payload.provider_id)

    # Only allow models this provider actually exposes. Checking the registry
    # prevents typos and stops a model string reaching the wrong upstream.
    known = await db.scalar(
        select(ProviderModel.id).where(
            ProviderModel.provider_id == provider.id,
            ProviderModel.model_id == payload.model_id,
        )
    )
    if known is None and payload.model_id != provider.default_model:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Model '{payload.model_id}' is not registered for this provider. "
                "Sync models first or pick one from the list."
            ),
        )

    messages = [m.model_dump() for m in payload.messages]

    async def event_stream() -> AsyncGenerator[str, None]:
        started = time.perf_counter()
        yield _sse(
            "start",
            {
                "provider_id": str(provider.id),
                "provider_name": provider.name,
                "model_id": payload.model_id,
            },
        )

        collected: list[str] = []
        try:
            llm = create_llm_client(
                provider,
                payload.model_id,
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
            if not final.strip():
                yield _sse(
                    "error",
                    {"message": "The model returned an empty response."},
                )
                return

            yield _sse(
                "done",
                {
                    "content": final,
                    "latency_ms": int((time.perf_counter() - started) * 1000),
                },
            )
        except httpx.TimeoutException:
            yield _sse("error", {"message": "The provider timed out."})
        except Exception as exc:  # noqa: BLE001 - surfaced to the operator
            # Many upstreams signal quota/auth problems through the client
            # library as generic exceptions; keep their text intact.
            yield _sse("error", {"message": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
