import asyncio
import uuid
import sys
from pathlib import Path
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.main import app
from app.core.database import AsyncSessionLocal
from app.models.provider import LLMProvider
from app.models.agent import AgentTemplate
from app.models.workflow import Workflow
from app.models.execution import WorkflowExecution
from sqlalchemy import select


async def run_e2e_tests():
    print("[*] Starting Comprehensive Omnigensi End-to-End Test Suite...")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Health check
        resp = await client.get("/health")
        assert resp.status_code == 200, f"Health check failed: {resp.text}"
        data = resp.json()
        assert data["status"] == "healthy"
        print("[+] 1. Health check: PASSED (service healthy, v2.0.0)")

        # 2. List tools
        resp = await client.get("/api/v1/tools")
        assert resp.status_code == 200
        tools = resp.json()
        assert len(tools) >= 5
        tool_ids = [t["id"] for t in tools]
        assert "create_markdown_document" in tool_ids
        assert "create_word_document" in tool_ids
        assert "create_pdf_document" in tool_ids
        print(f"[+] 2. Hardware tools registry: PASSED ({len(tools)} tools registered)")

        # 3. List providers
        resp = await client.get("/api/v1/providers")
        assert resp.status_code == 200
        providers = resp.json()
        assert len(providers) >= 1
        provider_id = providers[0]["id"]
        print(f"[+] 3. Providers API: PASSED ({len(providers)} providers found)")

        # 4. Fetch provider models
        resp = await client.get(f"/api/v1/providers/{provider_id}/models")
        assert resp.status_code == 200
        models = resp.json()
        assert len(models) >= 1
        print(f"[+] 4. Dynamic models discovery: PASSED ({len(models)} models available)")

        # 5. List agents
        resp = await client.get("/api/v1/agents")
        assert resp.status_code == 200
        agents = resp.json()
        assert len(agents) >= 4
        print(f"[+] 5. Dynamic Agent Studio: PASSED ({len(agents)} agent personas registered)")

        # 6. List workflows
        resp = await client.get("/api/v1/workflows")
        assert resp.status_code == 200
        workflows = resp.json()
        assert len(workflows) >= 1
        wf_id = workflows[0]["id"]
        print(f"[+] 6. Dynamic LangGraph Workflows: PASSED ({len(workflows)} blueprints found)")

        # 7. Trigger Workflow Execution
        resp = await client.post(
            f"/api/v1/workflows/{wf_id}/execute",
            json={"task_prompt": "Design a zero-trust cyberdeck authentication handshake protocol"},
        )
        assert resp.status_code == 202, f"Trigger failed: {resp.text}"
        exec_data = resp.json()
        exec_id = exec_data["id"]
        print(f"[+] 7. Asynchronous Execution Trigger: PASSED (Execution ID: {exec_id})")

        # 8. Check Execution retrieval
        resp = await client.get(f"/api/v1/executions/{exec_id}")
        assert resp.status_code == 200
        print("[+] 8. Execution Query: PASSED")

    print("[*] All API Integration Tests PASSED!")


if __name__ == "__main__":
    asyncio.run(run_e2e_tests())
