"""Aggregate metrics for dashboards (web command center and mobile home)."""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.engine.mcp_bridge import mcp_manager
from app.engine.tool_registry import AVAILABLE_TOOLS_METADATA
from app.models.agent import AgentTemplate
from app.models.execution import WorkflowExecution
from app.models.provider import LLMProvider
from app.models.workflow import Workflow
from app.schemas.system import ExecutionStatusBreakdown, SystemStatsResponse

router = APIRouter(prefix="/stats", tags=["System"])

KNOWN_STATUSES = (
    "completed",
    "failed",
    "running",
    "pending",
    "waiting_approval",
    "cancelled",
)


@router.get("", response_model=SystemStatsResponse)
async def get_system_stats(db: AsyncSession = Depends(get_db)) -> Any:
    """One call that returns every number the dashboard renders.

    Counting rows and summing tokens/cost server-side avoids the client
    paging through collections and silently under-reporting past one page.
    """
    providers = await db.scalar(select(func.count()).select_from(LLMProvider)) or 0
    providers_active = (
        await db.scalar(
            select(func.count())
            .select_from(LLMProvider)
            .where(LLMProvider.is_active.is_(True))
        )
        or 0
    )
    agents = await db.scalar(select(func.count()).select_from(AgentTemplate)) or 0
    workflows = await db.scalar(select(func.count()).select_from(Workflow)) or 0

    status_rows = await db.execute(
        select(WorkflowExecution.status, func.count()).group_by(
            WorkflowExecution.status
        )
    )
    counts = {status: count for status, count in status_rows.all()}

    total_tokens = (
        await db.scalar(select(func.coalesce(func.sum(WorkflowExecution.total_tokens), 0)))
        or 0
    )
    total_cost = (
        await db.scalar(
            select(func.coalesce(func.sum(WorkflowExecution.estimated_cost_usd), 0))
        )
        or 0
    )

    mcp_servers = mcp_manager.list_servers()

    return SystemStatsResponse(
        providers=providers,
        providers_active=providers_active,
        agents=agents,
        workflows=workflows,
        executions=ExecutionStatusBreakdown(
            total=sum(counts.values()),
            **{status: counts.get(status, 0) for status in KNOWN_STATUSES},
        ),
        total_tokens=int(total_tokens),
        estimated_cost_usd=float(total_cost),
        mcp_servers=len(mcp_servers),
        mcp_servers_enabled=sum(1 for s in mcp_servers if s.enabled),
        tools_available=len(AVAILABLE_TOOLS_METADATA),
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
