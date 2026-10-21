import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Any, Optional
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Header, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Pagination
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
from app.schemas.system import ActionAck
from app.engine.publisher import ExecutionPublisher
from app.engine.compiler import compile_workflow_graph
from app.engine.tool_registry import create_markdown_document, create_word_document, create_pdf_document
from app.engine.token_cost import calculate_execution_summary

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/executions", tags=["Workflow Executions"])

# Registry of active background execution tasks
ACTIVE_EXECUTION_TASKS: dict[str, asyncio.Task] = {}


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

        except asyncio.CancelledError:
            logger.info(f"Execution {execution_id} was aborted by operator")
            try:
                async with AsyncSessionLocal() as db_cancel:
                    exec_obj = await db_cancel.get(WorkflowExecution, execution_id)
                    if exec_obj and exec_obj.status == "running":
                        exec_obj.status = "cancelled"
                        exec_obj.final_output = "Execution aborted by operator."
                        exec_obj.completed_at = datetime.now(timezone.utc)
                        await db_cancel.commit()
                await publisher.publish(
                    "workflow_failed",
                    {"status": "cancelled", "error": "Execution aborted by operator."},
                )
            except Exception as e_cancel:
                logger.error(f"Error handling task cancellation: {e_cancel}")
            raise
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
            ACTIVE_EXECUTION_TASKS.pop(str(execution_id), None)
            await publisher.close()


async def _dispatch_execution(
    db: AsyncSession, workflow: Workflow, task_prompt: str
) -> WorkflowExecution:
    """Creates the execution row and starts the background run.

    Shared by the execute and retry endpoints so both produce identical
    records and telemetry.
    """
    execution = WorkflowExecution(
        workflow_id=workflow.id,
        status="running",
        task_prompt=task_prompt,
        generated_files=[],
        execution_logs=[],
        total_tokens=0,
        estimated_cost_usd=0.0,
        started_at=datetime.now(timezone.utc),
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    task = asyncio.create_task(
        run_execution_background(
            execution.id,
            workflow.id,
            task_prompt,
        )
    )
    ACTIVE_EXECUTION_TASKS[str(execution.id)] = task
    return execution


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

    execution = await _dispatch_execution(db, workflow, payload.task_prompt)
    return ExecutionResponse.model_validate(execution)


@router.get("", response_model=List[ExecutionResponse])
async def list_executions(
    response: Response,
    page: Pagination = Depends(),
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by execution status (completed, failed, running, ...)",
    ),
    workflow_id: Optional[uuid.UUID] = Query(
        None, description="Only return executions of this workflow"
    ),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Paginated execution history with optional status/workflow filters.

    Filters are applied server-side so a mobile client can render an
    "active runs" or per-workflow screen without downloading everything.
    """
    filters = []
    if status_filter:
        filters.append(WorkflowExecution.status == status_filter)
    if workflow_id:
        filters.append(WorkflowExecution.workflow_id == workflow_id)

    total_stmt = select(func.count()).select_from(WorkflowExecution)
    list_stmt = select(WorkflowExecution)
    if filters:
        total_stmt = total_stmt.where(*filters)
        list_stmt = list_stmt.where(*filters)

    total = await db.scalar(total_stmt) or 0
    result = await db.execute(
        list_stmt.order_by(WorkflowExecution.started_at.desc())
        .limit(page.limit)
        .offset(page.offset)
    )
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Limit"] = str(page.limit)
    response.headers["X-Offset"] = str(page.offset)
    return [ExecutionResponse.model_validate(e) for e in result.scalars().all()]


@router.get("/{execution_id}", response_model=ExecutionResponse)
async def get_execution(
    execution_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> Any:
    execution = await db.get(WorkflowExecution, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return ExecutionResponse.model_validate(execution)


@router.post(
    "/{execution_id}/retry",
    response_model=ExecutionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_execution(
    execution_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> Any:
    """Re-runs a past execution with the same workflow and prompt.

    Creates a new execution rather than mutating history, so the original run
    stays intact for comparison.
    """
    execution = await db.get(WorkflowExecution, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    if execution.status in ("running", "pending", "waiting_approval"):
        raise HTTPException(
            status_code=409,
            detail=f"Execution is still {execution.status}; cancel it before retrying",
        )

    workflow = await db.get(Workflow, execution.workflow_id)
    if not workflow:
        raise HTTPException(
            status_code=409,
            detail="The workflow for this execution no longer exists",
        )

    retried = await _dispatch_execution(db, workflow, execution.task_prompt)
    return ExecutionResponse.model_validate(retried)


@router.delete("/{execution_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_execution(
    execution_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> None:
    """Removes one execution from history.

    Refuses to delete a run that is still active so a background task cannot
    resurrect a row the client just removed.
    """
    execution = await db.get(WorkflowExecution, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    if execution.status in ("running", "pending", "waiting_approval"):
        raise HTTPException(
            status_code=409,
            detail=f"Execution is still {execution.status}; cancel it before deleting",
        )

    await db.delete(execution)
    await db.commit()


@router.post(
    "/{execution_id}/approve-tool",
    response_model=ActionAck,
    tags=["Workflow Executions"],
)
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
    return ActionAck(status="ok", message="Approval status broadcasted")


@router.post(
    "/{execution_id}/cancel",
    response_model=ActionAck,
    tags=["Workflow Executions"],
)
async def cancel_execution(
    execution_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Aborts a running workflow execution, cancels active background tasks,
    updates state to 'cancelled', and notifies SSE subscribers.
    """
    execution = await db.get(WorkflowExecution, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    if execution.status in ("completed", "failed", "cancelled"):
        return ActionAck(
            status="ok", message=f"Execution already {execution.status}"
        )

    # Cancel in-memory task
    task = ACTIVE_EXECUTION_TASKS.get(str(execution_id))
    if task and not task.done():
        task.cancel()

    execution.status = "cancelled"
    execution.final_output = "Execution aborted by operator."
    execution.completed_at = datetime.now(timezone.utc)
    await db.commit()

    publisher = ExecutionPublisher(str(execution_id))
    await publisher.publish(
        "workflow_failed",
        {"status": "cancelled", "error": "Execution aborted by operator."},
    )
    await publisher.close()

    return ActionAck(status="cancelled", message="Execution cancelled successfully")


@router.get("/{execution_id}/stream")
async def stream_execution_telemetry(
    execution_id: uuid.UUID,
    last_event_id: Optional[str] = Header(
        None,
        alias="Last-Event-ID",
        description="Highest event id already received; used to replay missed events",
    ),
) -> StreamingResponse:
    """
    Real-time Server-Sent Events (SSE) telemetry stream.

    Every frame carries a monotonically increasing ``id:``. When a client
    reconnects it may send ``Last-Event-ID`` and the server replays the
    persisted event history from that point before continuing live, so a
    phone that lost its connection does not silently miss telemetry.
    """
    channel_name = f"execution:{execution_id}"

    def _parse_cursor(raw: Optional[str]) -> int:
        try:
            return max(0, int(raw)) if raw is not None else 0
        except (TypeError, ValueError):
            return 0

    resume_from = _parse_cursor(last_event_id)

    async def sse_event_generator():
        event_id = 0
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        pubsub = r.pubsub()
        await pubsub.subscribe(channel_name)

        async def _terminal_payload(exec_obj) -> dict:
            return {
                "status": exec_obj.status,
                "final_output": exec_obj.final_output,
                "generated_files": exec_obj.generated_files or [],
                "total_tokens": exec_obj.total_tokens or 0,
                "estimated_cost_usd": float(exec_obj.estimated_cost_usd or 0),
            }

        # Initial ping to establish connection immediately
        yield f"event: connected\nid: 0\ndata: {json.dumps({'execution_id': str(execution_id), 'timestamp': datetime.now(timezone.utc).isoformat(), 'resumed_from': resume_from})}\n\n"

        # Replay persisted telemetry when the client reconnects after a drop.
        if resume_from > 0:
            async with AsyncSessionLocal() as db_replay:
                exec_obj = await db_replay.get(WorkflowExecution, execution_id)
                if exec_obj and exec_obj.execution_logs:
                    for idx, entry in enumerate(exec_obj.execution_logs, start=1):
                        if idx <= resume_from:
                            continue
                        evt_type = (
                            entry.get("type") or entry.get("event") or "message"
                        )
                        payload = entry.get("data", entry)
                        event_id = idx
                        yield f"event: {evt_type}\nid: {event_id}\ndata: {json.dumps(payload, default=str)}\n\n"

        # Check if execution already completed before SSE connected
        async with AsyncSessionLocal() as db_check:
            exec_obj = await db_check.get(WorkflowExecution, execution_id)
            if exec_obj and exec_obj.status in ("completed", "failed", "cancelled"):
                evt_type = "workflow_complete" if exec_obj.status == "completed" else "workflow_failed"
                payload = {
                    "status": exec_obj.status,
                    "final_output": exec_obj.final_output,
                    "generated_files": exec_obj.generated_files or [],
                    "total_tokens": exec_obj.total_tokens or 0,
                    "estimated_cost_usd": float(exec_obj.estimated_cost_usd or 0),
                }
                yield f"event: {evt_type}\nid: {resume_from + 1}\ndata: {json.dumps(payload)}\n\n"
                await pubsub.unsubscribe(channel_name)
                await pubsub.aclose()
                await r.aclose()
                return

        idle_ticks = 0
        try:
            while True:
                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=0.5
                )
                if msg is not None:
                    idle_ticks = 0
                    raw_data = msg.get("data")
                    if isinstance(raw_data, str):
                        try:
                            parsed = json.loads(raw_data)
                            evt_type = parsed.get("type", "message")
                            payload_str = json.dumps(parsed.get("data", {}))
                            event_id += 1
                            yield f"event: {evt_type}\nid: {resume_from + event_id}\ndata: {payload_str}\n\n"

                            if evt_type in ("workflow_complete", "workflow_failed"):
                                break
                        except Exception:
                            event_id += 1
                            yield f"event: message\nid: {resume_from + event_id}\ndata: {raw_data}\n\n"
                else:
                    idle_ticks += 1
                    # Keep-alive heartbeat comment
                    yield ": ping\n\n"
                    # Periodically check DB in case of race condition
                    if idle_ticks % 4 == 0:
                        async with AsyncSessionLocal() as db_check:
                            exec_obj = await db_check.get(WorkflowExecution, execution_id)
                            if exec_obj and exec_obj.status in ("completed", "failed", "cancelled"):
                                evt_type = "workflow_complete" if exec_obj.status == "completed" else "workflow_failed"
                                payload = {
                                    "status": exec_obj.status,
                                    "final_output": exec_obj.final_output,
                                    "generated_files": exec_obj.generated_files or [],
                                    "total_tokens": exec_obj.total_tokens or 0,
                                    "estimated_cost_usd": float(exec_obj.estimated_cost_usd or 0),
                                }
                                event_id += 1
                                yield f"event: {evt_type}\nid: {resume_from + event_id}\ndata: {json.dumps(payload)}\n\n"
                                break
                    await asyncio.sleep(0.3)
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
