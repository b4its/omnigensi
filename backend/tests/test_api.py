import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_health_check_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=auth_headers()
    ) as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["version"] == "2.0.0"


@pytest.mark.asyncio
async def test_tools_list_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=auth_headers()
    ) as client:
        resp = await client.get("/api/v1/tools")
        assert resp.status_code == 200
        tools = resp.json()
        assert len(tools) >= 5
        tool_ids = [t["id"] for t in tools]
        assert "create_markdown_document" in tool_ids
        assert "create_word_document" in tool_ids
        assert "create_pdf_document" in tool_ids
        assert "create_code_file" in tool_ids


@pytest.mark.asyncio
async def test_providers_and_agents_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=auth_headers()
    ) as client:
        # Providers
        resp = await client.get("/api/v1/providers")
        assert resp.status_code == 200
        providers = resp.json()
        assert len(providers) >= 1
        p_id = providers[0]["id"]

        # Models: always 200, containing live models or the stored registry.
        # It must never invent models for an unreachable provider.
        resp_models = await client.get(f"/api/v1/providers/{p_id}/models")
        assert resp_models.status_code == 200
        assert isinstance(resp_models.json(), list)

        # Agents
        resp_agents = await client.get("/api/v1/agents")
        assert resp_agents.status_code == 200
        agents = resp_agents.json()
        assert len(agents) >= 4

        # Workflows
        resp_wf = await client.get("/api/v1/workflows")
        assert resp_wf.status_code == 200
        workflows = resp_wf.json()
        assert len(workflows) >= 1


@pytest.mark.asyncio
async def test_cancel_execution_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=auth_headers()
    ) as client:
        # Get workflow
        resp_wf = await client.get("/api/v1/workflows")
        assert resp_wf.status_code == 200
        wf_id = resp_wf.json()[0]["id"]

        # Trigger execution
        resp_exec = await client.post(
            f"/api/v1/executions/workflows/{wf_id}/execute",
            json={"task_prompt": "Testing cancellation pipeline"},
        )
        assert resp_exec.status_code == 202
        exec_id = resp_exec.json()["id"]

        # Immediately cancel
        resp_cancel = await client.post(f"/api/v1/executions/{exec_id}/cancel")
        assert resp_cancel.status_code == 200
        data = resp_cancel.json()
        assert data["status"] in ("cancelled", "ok")

        # Verify execution record has cancelled or completed
        resp_check = await client.get(f"/api/v1/executions/{exec_id}")
        assert resp_check.status_code == 200
        assert resp_check.json()["status"] in ("cancelled", "completed")
