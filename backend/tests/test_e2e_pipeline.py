import os
import json
import base64
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import AsyncSessionLocal
from app.models.workflow import Workflow
from app.models.execution import WorkflowExecution
from sqlalchemy import select


@pytest.mark.asyncio
async def test_full_e2e_pipeline_execution():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Workflow).limit(1))
        wf = res.scalars().first()
        assert wf is not None, "At least one workflow must exist (run seed.py)"
        wf_id = wf.id

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Trigger execution
        launch_res = await client.post(
            f"/api/v1/workflows/{wf_id}/execute",
            json={"task_prompt": "Build a zero-trust cyberdeck authentication subsystem"},
        )
        assert launch_res.status_code == 202
        exec_data = launch_res.json()
        exec_id = exec_data["id"]

        # Connect to stream
        events_received = []
        async with client.stream("GET", f"/api/v1/executions/{exec_id}/stream") as stream:
            async for line in stream.aiter_lines():
                if line.startswith("event:"):
                    evt_type = line.split(":", 1)[1].strip()
                    events_received.append(evt_type)
                    if evt_type in ("workflow_complete", "workflow_failed"):
                        break

        assert "connected" in events_received
        assert "workflow_complete" in events_received

        # Verify DB state
        async with AsyncSessionLocal() as db:
            execution = await db.get(WorkflowExecution, uuid.UUID(exec_id))
            assert execution is not None
            assert execution.status == "completed"
            assert execution.total_tokens > 0
            assert execution.estimated_cost_usd > 0
            assert len(execution.generated_files) > 0

            # Verify files on disk in workspace
            for f_meta in execution.generated_files:
                f_path = f_meta["filepath"]
                assert os.path.exists(f_path)
                assert os.path.getsize(f_path) > 0
                assert f_meta["content_base64"]
                # Verify base64 is valid
                decoded = base64.b64decode(f_meta["content_base64"])
                assert len(decoded) > 0
