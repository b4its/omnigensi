import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_health_check_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["version"] == "2.0.0"


@pytest.mark.asyncio
async def test_tools_list_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/tools")
        assert resp.status_code == 200
        tools = resp.json()
        assert len(tools) >= 5
        tool_ids = [t["id"] for t in tools]
        assert "create_markdown_document" in tool_ids
        assert "create_word_document" in tool_ids
        assert "create_pdf_document" in tool_ids


@pytest.mark.asyncio
async def test_providers_and_agents_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Providers
        resp = await client.get("/api/v1/providers")
        assert resp.status_code == 200
        providers = resp.json()
        assert len(providers) >= 1
        p_id = providers[0]["id"]

        # Models
        resp_models = await client.get(f"/api/v1/providers/{p_id}/models")
        assert resp_models.status_code == 200
        models = resp_models.json()
        assert len(models) > 0

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
