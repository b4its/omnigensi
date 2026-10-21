import uuid
from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Pagination
from app.core.database import get_db
from app.models.workflow import Workflow
from app.schemas.workflow import (
    WorkflowCreate,
    WorkflowUpdate,
    WorkflowResponse,
)

router = APIRouter(prefix="/workflows", tags=["Workflows"])


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    payload: WorkflowCreate, db: AsyncSession = Depends(get_db)
) -> Any:
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


@router.get("", response_model=List[WorkflowResponse])
async def list_workflows(
    response: Response,
    page: Pagination = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Any:
    total = await db.scalar(select(func.count()).select_from(Workflow)) or 0
    result = await db.execute(
        select(Workflow)
        .order_by(Workflow.created_at.desc())
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


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: uuid.UUID,
    payload: WorkflowUpdate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    workflow = await db.get(Workflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    if payload.name is not None:
        workflow.name = payload.name
    if payload.description is not None:
        workflow.description = payload.description
    if payload.max_revisions is not None:
        workflow.max_revisions = payload.max_revisions
    if payload.graph_schema is not None:
        workflow.graph_schema = payload.graph_schema

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
