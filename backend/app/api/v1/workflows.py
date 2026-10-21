import uuid
from typing import List, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Pagination
from app.core.database import get_db
from app.engine.graph_validation import validate_graph
from app.models.agent import AgentTemplate
from app.models.workflow import Workflow
from app.schemas.workflow import (
    GraphValidationResponse,
    WorkflowCreate,
    WorkflowDuplicateRequest,
    WorkflowResponse,
    WorkflowUpdate,
)

router = APIRouter(prefix="/workflows", tags=["Workflows"])


async def _known_agent_ids(db: AsyncSession) -> set[str]:
    rows = await db.execute(select(AgentTemplate.id))
    return {str(r) for r in rows.scalars().all()}


def _reject_invalid(graph_schema: Any, known_agents: set[str]) -> None:
    """Saves must not persist a graph that cannot run."""
    result = validate_graph(graph_schema, known_agents)
    if not result.valid:
        raise HTTPException(status_code=400, detail=result.summary())


def _to_validation_response(result) -> GraphValidationResponse:
    return GraphValidationResponse(
        valid=result.valid,
        summary=result.summary(),
        node_count=result.node_count,
        edge_count=result.edge_count,
        entry_point=result.entry_point,
        issues=result.errors,
    )


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    payload: WorkflowCreate, db: AsyncSession = Depends(get_db)
) -> Any:
    _reject_invalid(payload.graph_schema, await _known_agent_ids(db))

    workflow = Workflow(
        name=payload.name,
        description=payload.description,
        max_revisions=payload.max_revisions,
        graph_schema=payload.graph_schema,
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return workflow


@router.post(
    "/validate",
    response_model=GraphValidationResponse,
    tags=["Workflows"],
)
async def validate_workflow_graph(
    payload: WorkflowCreate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Dry-run a graph before saving it.

    Returns every structural problem at once so an editor (web or mobile) can
    highlight fields instead of failing later inside a background execution.
    """
    result = validate_graph(payload.graph_schema, await _known_agent_ids(db))
    return _to_validation_response(result)


@router.get("", response_model=List[WorkflowResponse])
async def list_workflows(
    response: Response,
    page: Pagination = Depends(),
    q: Optional[str] = Query(None, max_length=120, description="Search by name"),
    db: AsyncSession = Depends(get_db),
) -> Any:
    filters = []
    if q:
        filters.append(Workflow.name.ilike(f"%{q}%"))

    total_stmt = select(func.count()).select_from(Workflow)
    list_stmt = select(Workflow)
    if filters:
        total_stmt = total_stmt.where(*filters)
        list_stmt = list_stmt.where(*filters)

    total = await db.scalar(total_stmt) or 0
    result = await db.execute(
        list_stmt.order_by(Workflow.created_at.desc())
        .limit(page.limit)
        .offset(page.offset)
    )
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Limit"] = str(page.limit)
    response.headers["X-Offset"] = str(page.offset)
    return result.scalars().all()


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> Any:
    workflow = await db.get(Workflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@router.get(
    "/{workflow_id}/validate",
    response_model=GraphValidationResponse,
)
async def validate_saved_workflow(
    workflow_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> Any:
    """Re-check a stored workflow, e.g. after an agent was deleted."""
    workflow = await db.get(Workflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    result = validate_graph(workflow.graph_schema, await _known_agent_ids(db))
    return _to_validation_response(result)


@router.post(
    "/{workflow_id}/duplicate",
    response_model=WorkflowResponse,
    status_code=status.HTTP_201_CREATED,
)
async def duplicate_workflow(
    workflow_id: uuid.UUID,
    payload: Optional[WorkflowDuplicateRequest] = None,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Clones a workflow so an operator can branch from an existing graph."""
    source = await db.get(Workflow, workflow_id)
    if not source:
        raise HTTPException(status_code=404, detail="Workflow not found")

    name = (payload.name if payload else None) or f"{source.name} (copy)"
    clone = Workflow(
        name=name[:150],
        description=source.description,
        max_revisions=source.max_revisions,
        graph_schema=source.graph_schema,
    )
    db.add(clone)
    await db.commit()
    await db.refresh(clone)
    return clone


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: uuid.UUID,
    payload: WorkflowUpdate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    workflow = await db.get(Workflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    if payload.graph_schema is not None:
        _reject_invalid(payload.graph_schema, await _known_agent_ids(db))
        workflow.graph_schema = payload.graph_schema
    if payload.name is not None:
        workflow.name = payload.name
    if payload.description is not None:
        workflow.description = payload.description
    if payload.max_revisions is not None:
        workflow.max_revisions = payload.max_revisions

    await db.commit()
    await db.refresh(workflow)
    return workflow


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> None:
    workflow = await db.get(Workflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    await db.delete(workflow)
    await db.commit()
