import uuid
from typing import List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Pagination
import time

from app.core.database import get_db
from app.engine.llm_factory import create_llm_client
from app.models.agent import AgentTemplate
from app.models.provider import LLMProvider
from app.schemas.agent import (
    AgentCreate,
    AgentDuplicateRequest,
    AgentResponse,
    AgentTestRequest,
    AgentTestResponse,
    AgentUpdate,
)
from app.engine.tool_registry import DEVICE_TOOL_MAP

router = APIRouter(prefix="/agents", tags=["Dynamic Agent Studio"])


def _validate_tools(tools_config: List[str]) -> None:
    for tool_name in tools_config:
        if tool_name not in DEVICE_TOOL_MAP:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown tool '{tool_name}'. Allowed tools: {list(DEVICE_TOOL_MAP.keys())}",
            )


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    payload: AgentCreate, db: AsyncSession = Depends(get_db)
) -> Any:
    # Verify provider exists
    provider = await db.get(LLMProvider, payload.provider_id)
    if not provider:
        raise HTTPException(status_code=400, detail="Provider not found")

    _validate_tools(payload.tools_config)

    agent = AgentTemplate(
        provider_id=payload.provider_id,
        name=payload.name,
        avatar_code=payload.avatar_code,
        role=payload.role,
        goal=payload.goal,
        backstory=payload.backstory,
        node_type=payload.node_type,
        model_name=payload.model_name,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
        tools_config=payload.tools_config,
        require_device_approval=payload.require_device_approval,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    return AgentResponse(
        id=agent.id,
        provider_id=agent.provider_id,
        provider_name=provider.name,
        name=agent.name,
        avatar_code=agent.avatar_code,
        role=agent.role,
        goal=agent.goal,
        backstory=agent.backstory,
        node_type=agent.node_type,
        model_name=agent.model_name,
        temperature=agent.temperature,
        max_tokens=agent.max_tokens,
        tools_config=agent.tools_config,
        require_device_approval=agent.require_device_approval,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


@router.get("", response_model=List[AgentResponse])
async def list_agents(
    response: Response,
    page: Pagination = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Any:
    total = await db.scalar(select(func.count()).select_from(AgentTemplate)) or 0
    query = (
        select(AgentTemplate)
        .options(selectinload(AgentTemplate.provider))
        .order_by(AgentTemplate.created_at.desc())
        .limit(page.limit)
        .offset(page.offset)
    )
    result = await db.execute(query)
    agents = result.scalars().all()
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Limit"] = str(page.limit)
    response.headers["X-Offset"] = str(page.offset)
    return [
        AgentResponse(
            id=a.id,
            provider_id=a.provider_id,
            provider_name=a.provider.name if a.provider else None,
            name=a.name,
            avatar_code=a.avatar_code,
            role=a.role,
            goal=a.goal,
            backstory=a.backstory,
            node_type=a.node_type,
            model_name=a.model_name,
            temperature=a.temperature,
            max_tokens=a.max_tokens,
            tools_config=a.tools_config,
            require_device_approval=a.require_device_approval,
            created_at=a.created_at,
            updated_at=a.updated_at,
        )
        for a in agents
    ]


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Any:
    query = (
        select(AgentTemplate)
        .options(selectinload(AgentTemplate.provider))
        .where(AgentTemplate.id == agent_id)
    )
    result = await db.execute(query)
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return AgentResponse(
        id=agent.id,
        provider_id=agent.provider_id,
        provider_name=agent.provider.name if agent.provider else None,
        name=agent.name,
        avatar_code=agent.avatar_code,
        role=agent.role,
        goal=agent.goal,
        backstory=agent.backstory,
        node_type=agent.node_type,
        model_name=agent.model_name,
        temperature=agent.temperature,
        max_tokens=agent.max_tokens,
        tools_config=agent.tools_config,
        require_device_approval=agent.require_device_approval,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: uuid.UUID,
    payload: AgentUpdate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    query = (
        select(AgentTemplate)
        .options(selectinload(AgentTemplate.provider))
        .where(AgentTemplate.id == agent_id)
    )
    result = await db.execute(query)
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if payload.provider_id is not None:
        provider = await db.get(LLMProvider, payload.provider_id)
        if not provider:
            raise HTTPException(status_code=400, detail="Provider not found")
        agent.provider_id = payload.provider_id

    if payload.tools_config is not None:
        _validate_tools(payload.tools_config)
        agent.tools_config = payload.tools_config

    if payload.name is not None:
        agent.name = payload.name
    if payload.avatar_code is not None:
        agent.avatar_code = payload.avatar_code
    if payload.role is not None:
        agent.role = payload.role
    if payload.goal is not None:
        agent.goal = payload.goal
    if payload.backstory is not None:
        agent.backstory = payload.backstory
    if payload.node_type is not None:
        agent.node_type = payload.node_type
    if payload.model_name is not None:
        agent.model_name = payload.model_name
    if payload.temperature is not None:
        agent.temperature = payload.temperature
    if payload.max_tokens is not None:
        agent.max_tokens = payload.max_tokens
    if payload.require_device_approval is not None:
        agent.require_device_approval = payload.require_device_approval

    await db.commit()
    await db.refresh(agent)

    return AgentResponse(
        id=agent.id,
        provider_id=agent.provider_id,
        provider_name=agent.provider.name if agent.provider else None,
        name=agent.name,
        avatar_code=agent.avatar_code,
        role=agent.role,
        goal=agent.goal,
        backstory=agent.backstory,
        node_type=agent.node_type,
        model_name=agent.model_name,
        temperature=agent.temperature,
        max_tokens=agent.max_tokens,
        tools_config=agent.tools_config,
        require_device_approval=agent.require_device_approval,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> None:
    agent = await db.get(AgentTemplate, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    await db.delete(agent)
    await db.commit()


@router.post("/{agent_id}/test", response_model=AgentTestResponse)
async def test_agent(
    agent_id: uuid.UUID,
    payload: AgentTestRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Runs one agent persona against its provider with a single prompt.

    Lets an operator sanity-check role/goal/backstory and the selected model
    without wiring a workflow, mirroring the provider chat test.
    """
    agent = (
        await db.execute(
            select(AgentTemplate)
            .options(selectinload(AgentTemplate.provider))
            .where(AgentTemplate.id == agent_id)
        )
    ).scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    provider = agent.provider
    if not provider:
        raise HTTPException(
            status_code=400, detail="Agent has no provider configured"
        )

    system_prompt = (
        f"You are {agent.name}.\n"
        f"Role: {agent.role}\n"
        f"Goal: {agent.goal}\n"
        f"Backstory: {agent.backstory}"
    )

    started = time.perf_counter()
    try:
        llm = create_llm_client(
            provider=provider,
            model_name=agent.model_name,
            temperature=agent.temperature,
            max_tokens=payload.max_tokens or min(agent.max_tokens or 512, 1024),
            streaming=False,
        )
        result = await llm.ainvoke(
            [
                ("system", system_prompt),
                ("human", payload.prompt),
            ]
        )
        latency = int((time.perf_counter() - started) * 1000)

        text = result.content if hasattr(result, "content") else str(result)
        if isinstance(text, list):
            text = " ".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in text
            )

        usage = getattr(result, "usage_metadata", None) or {}
        return AgentTestResponse(
            ok=True,
            agent_id=agent.id,
            agent_name=agent.name,
            model_name=agent.model_name,
            provider_name=provider.name,
            response_text=(text or "").strip(),
            latency_ms=latency,
            prompt_tokens=usage.get("input_tokens"),
            completion_tokens=usage.get("output_tokens"),
        )
    except Exception as exc:  # noqa: BLE001 - surfaced to the operator
        return AgentTestResponse(
            ok=False,
            agent_id=agent.id,
            agent_name=agent.name,
            model_name=agent.model_name,
            provider_name=provider.name,
            latency_ms=int((time.perf_counter() - started) * 1000),
            error=str(exc),
        )


@router.post(
    "/{agent_id}/duplicate",
    response_model=AgentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def duplicate_agent(
    agent_id: uuid.UUID,
    payload: Optional[AgentDuplicateRequest] = None,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Clones an agent persona so a variant can be built quickly."""
    source = await db.get(AgentTemplate, agent_id)
    if not source:
        raise HTTPException(status_code=404, detail="Agent not found")

    name = (payload.name if payload else None) or f"{source.name} (copy)"
    clone = AgentTemplate(
        provider_id=source.provider_id,
        name=name[:120],
        avatar_code=source.avatar_code,
        role=source.role,
        goal=source.goal,
        backstory=source.backstory,
        node_type=source.node_type,
        model_name=source.model_name,
        temperature=source.temperature,
        max_tokens=source.max_tokens,
        tools_config=list(source.tools_config or []),
        require_device_approval=source.require_device_approval,
    )
    db.add(clone)
    await db.commit()
    await db.refresh(clone)
    return AgentResponse.model_validate(clone)
