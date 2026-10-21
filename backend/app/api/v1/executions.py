import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Any, Optional
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db, AsyncSessionLocal
from app.models.workflow import Workflow
from app.models.execution import WorkflowExecution
from app.models.agent import AgentTemplate
from app.models.provider import LLMProvider
from app.schemas.execution import (
    ExecutionCreate,
    ExecutionResponse,
    ToolApprovalRequest,
)
from app.engine.publisher import ExecutionPublisher
from app.engine.compiler import compile_workflow_graph
from app.engine.tool_registry import create_markdown_document, create_word_document, create_pdf_document
from app.engine.token_cost import calculate_execution_summary

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/executions", tags=["Workflow Executions"])


async def run_execution_background(
    execution_id: uuid.UUID,
    workflow_id: uuid.UUID,
    task_prompt: str,
) -> None:
    """
    Background runner that executes the compiled LangGraph workflow.
    Publishes real-time telemetry to Redis and updates the database state upon completion.
    """
    publisher = ExecutionPublisher(str(execution_id))
    async with AsyncSessionLocal() as db:
        execution = await db.get(WorkflowExecution, execution_id)
        workflow = await db.get(Workflow, workflow_id)

        if not execution or not workflow:
            logger.error(f"Execution {execution_id} or Workflow {workflow_id} not found in DB")
            await publisher.close()
            return

        try:
            # 1. Fetch all agents and providers needed
            q_agents = await db.execute(select(AgentTemplate))
            agents_by_id = {str(a.id): a for a in q_agents.scalars().all()}

            q_providers = await db.execute(select(LLMProvider))
            providers_by_id = {str(p.id): p for p in q_providers.scalars().all()}

            # 2. Compile LangGraph
            compiled_graph = compile_workflow_graph(
                workflow_schema=workflow.graph_schema,
                agents_by_id=agents_by_id,
                providers_by_id=providers_by_id,
                max_revisions=workflow.max_revisions,
                publisher=publisher,
            )

            # 3. Initial State
            initial_state = {
                "task_prompt": task_prompt,
                "shared_context": "",
                "current_draft": "",
                "reviewer_feedback": "",
                "is_approved": False,
                "revision_count": 0,
                "generated_files": [],
                "execution_history": [],
            }

            # 4. Execute Graph
            final_state = await compiled_graph.ainvoke(initial_state)

            # 5. Extract output and generated files
            final_output = final_state.get("current_draft") or final_state.get("shared_context") or "Workflow executed successfully."
            generated_files = final_state.get("generated_files", [])
            execution_history = final_state.get("execution_history", [])

            # Determine model name for cost calculation
            primary_model = "gpt-4o"
            if workflow.graph_schema and "nodes" in workflow.graph_schema:
                for n in workflow.graph_schema["nodes"]:
                    a_id = str(n.get("agent_id"))
                    if a_id in agents_by_id:
                        primary_model = agents_by_id[a_id].model_name
                        break

            metrics = calculate_execution_summary(
                task_prompt=task_prompt,
                execution_logs=execution_history,
                model_name=primary_model,
            )

            # Update DB
            execution.status = "completed"
            execution.final_output = final_output
            execution.generated_files = generated_files
            execution.execution_logs = execution_history
            execution.total_tokens = metrics["total_tokens"]
            execution.estimated_cost_usd = metrics["estimated_cost_usd"]
            execution.completed_at = datetime.now(timezone.utc)
            await db.commit()

            # Publish completion event
            await publisher.publish(
                "workflow_complete",
                {
                    "status": "completed",
                    "final_output": final_output,
                    "generated_files": generated_files,
                    "execution_logs": execution_history,
                    "total_tokens": execution.total_tokens,
                    "estimated_cost_usd": float(execution.estimated_cost_usd),
                },
            )

        except Exception as e:
            logger.error(f"Error during graph execution: {e}", exc_info=True)
            execution.status = "failed"
            execution.final_output = f"Execution halted with error: {str(e)}"
            execution.completed_at = datetime.now(timezone.utc)
            await db.commit()

            await publisher.publish(
                "workflow_failed",
                {"status": "failed", "error": str(e)},
            )
        finally:
            await publisher.close()


@router.post("/workflows/{workflow_id}/execute", response_model=ExecutionResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_workflow_execution(
    workflow_id: uuid.UUID,
    payload: ExecutionCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> Any:
    workflow = await db.get(Workflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    execution = WorkflowExecution(
        workflow_id=workflow.id,
        status="running",
        task_prompt=payload.task_prompt,
        generated_files=[],
        execution_logs=[],
        total_tokens=0,
        estimated_cost_usd=0.0,
        started_at=datetime.now(timezone.utc),
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    background_tasks.add_task(
        run_execution_background,
        execution.id,
        workflow.id,
        payload.task_prompt,
    )

    return ExecutionResponse.model_validate(execution)


@router.get("", response_model=List[ExecutionResponse])
async def list_executions(db: AsyncSession = Depends(get_db)) -> Any:
    result = await db.execute(
        select(WorkflowExecution).order_by(WorkflowExecution.started_at.desc()).limit(50)
    )
    return [ExecutionResponse.model_validate(e) for e in result.scalars().all()]


@router.get("/{execution_id}", response_model=ExecutionResponse)
async def get_execution(
    execution_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> Any:
    execution = await db.get(WorkflowExecution, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return ExecutionResponse.model_validate(execution)


@router.post("/{execution_id}/approve-tool")
async def approve_tool_execution(
    execution_id: uuid.UUID,
    payload: ToolApprovalRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    execution = await db.get(WorkflowExecution, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    publisher = ExecutionPublisher(str(execution_id))
    await publisher.publish(
        "tool_approval_response",
        {
            "tool_call_id": payload.tool_call_id,
            "approved": payload.approved,
            "notes": payload.notes,
        },
    )
    await publisher.close()
    return {"status": "ok", "message": "Approval status broadcasted"}


@router.get("/{execution_id}/stream")
async def stream_execution_telemetry(execution_id: uuid.UUID) -> StreamingResponse:
    """
    Real-time Server-Sent Events (SSE) telemetry stream.
    Transmits agent thought processes, token chunks, reviewer loops, and device file write payloads.
    """
    channel_name = f"execution:{execution_id}"

    async def sse_event_generator():
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        pubsub = r.pubsub()
        await pubsub.subscribe(channel_name)

        # Initial ping to establish connection immediately
        yield f"event: connected\ndata: {json.dumps({'execution_id': str(execution_id), 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"

        try:
            while True:
                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if msg is not None:
                    raw_data = msg.get("data")
                    if isinstance(raw_data, str):
                        try:
                            parsed = json.loads(raw_data)
                            evt_type = parsed.get("type", "message")
                            payload_str = json.dumps(parsed.get("data", {}))
                            yield f"event: {evt_type}\ndata: {payload_str}\n\n"

                            if evt_type in ("workflow_complete", "workflow_failed"):
                                break
                        except Exception:
                            yield f"event: message\ndata: {raw_data}\n\n"
                else:
                    # Keep-alive heartbeat comment
                    yield ": ping\n\n"
                    await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(channel_name)
            await pubsub.aclose()
            await r.aclose()

    return StreamingResponse(
        sse_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
