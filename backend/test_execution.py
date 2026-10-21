import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.workflow import Workflow
from app.models.execution import WorkflowExecution
from app.api.v1.executions import run_execution_background
import uuid
from datetime import datetime, timezone


async def main():
    print("[*] Starting backend workflow execution test...")
    async with AsyncSessionLocal() as session:
        # Get first workflow
        q = await session.execute(select(Workflow).limit(1))
        wf = q.scalar_one_or_none()
        assert wf is not None, "Workflow not found"
        print(f"[+] Loaded workflow: {wf.name} (id: {wf.id})")

        execution = WorkflowExecution(
            id=uuid.uuid4(),
            workflow_id=wf.id,
            status="running",
            task_prompt="Build a resilient high-throughput payment settlement microservice architecture",
            generated_files=[],
            execution_logs=[],
            total_tokens=0,
            estimated_cost_usd=0.0,
            started_at=datetime.now(timezone.utc),
        )
        session.add(execution)
        await session.commit()
        await session.refresh(execution)
        print(f"[+] Created execution: {execution.id}")

    print("[*] Running execution in background handler...")
    await run_execution_background(
        execution_id=execution.id,
        workflow_id=wf.id,
        task_prompt=execution.task_prompt,
    )

    async with AsyncSessionLocal() as session:
        updated = await session.get(WorkflowExecution, execution.id)
        print(f"[+] Execution completed with status: {updated.status}")
        print(f"[+] Total generated files: {len(updated.generated_files)}")
        for f in updated.generated_files:
            print(f"    - {f.get('filename')} ({f.get('file_type')}, {f.get('size_bytes')} bytes)")
        print(f"[+] Execution history steps: {len(updated.execution_logs)}")
        for log in updated.execution_logs:
            print(f"    - Step: {log.get('node_id')} ({log.get('agent_name')})")

    print("[*] Test finished successfully!")


if __name__ == "__main__":
    asyncio.run(main())
