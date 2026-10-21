"""Tests for agent testing/duplication, standalone tools and execution retry."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


def _client() -> AsyncClient:
    """Authenticated client; the API is password protected."""
    from tests.conftest import make_client

    return make_client(authenticated=True)


async def _first_agent(client: AsyncClient) -> dict:
    agents = (await client.get("/api/v1/agents?limit=1")).json()
    assert agents
    return agents[0]


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tools_endpoint_is_typed_with_parameters():
    async with _client() as client:
        resp = await client.get("/api/v1/tools")
        assert resp.status_code == 200
        tools = resp.json()
        assert tools

        by_id = {t["id"]: t for t in tools}
        markdown = by_id["create_markdown_document"]
        # Parameters must be discoverable so clients can render a form.
        assert markdown["parameters"] == ["filename", "content"]
        assert markdown["requires_write"] is True
        assert markdown["category"] == "document"


@pytest.mark.asyncio
async def test_tool_execute_writes_a_real_file():
    async with _client() as client:
        resp = await client.post(
            "/api/v1/tools/create_markdown_document/execute",
            json={"arguments": {"filename": "tool_exec_test.md", "content": "# hi"}},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["result"]["status"] == "success"
        assert body["result"]["filename"] == "tool_exec_test.md"

        # The file must be downloadable through the public endpoint.
        dl = await client.get("/api/v1/files/tool_exec_test.md")
        assert dl.status_code == 200
        assert dl.content == b"# hi"

        from app.core.config import settings

        (settings.workspace_path / "tool_exec_test.md").unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_tool_execute_rejects_unknown_arguments():
    async with _client() as client:
        resp = await client.post(
            "/api/v1/tools/create_markdown_document/execute",
            json={"arguments": {"nope": 1}},
        )
        assert resp.status_code == 400
        assert "Unknown argument" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_tool_execute_unknown_tool_404():
    async with _client() as client:
        resp = await client.post(
            "/api/v1/tools/not_a_tool/execute", json={"arguments": {}}
        )
        assert resp.status_code == 404
        assert resp.json()["code"] == "not_found"


# --------------------------------------------------------------------------
# Agents
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_agent_test_returns_structured_result():
    """A failing provider must report ok=false, never a fake success."""
    async with _client() as client:
        agent = await _first_agent(client)
        resp = await client.post(
            f"/api/v1/agents/{agent['id']}/test", json={"prompt": "Say hi"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["agent_id"] == agent["id"]
        assert body["agent_name"] == agent["name"]
        assert body["model_name"] == agent["model_name"]
        assert isinstance(body["latency_ms"], int)
        # Either a reply or an error, never both/neither.
        assert body["ok"] is True or body["error"]


@pytest.mark.asyncio
async def test_agent_test_unknown_agent_404():
    async with _client() as client:
        resp = await client.post(
            "/api/v1/agents/00000000-0000-0000-0000-000000000000/test",
            json={"prompt": "hi"},
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_agent_test_validates_prompt():
    async with _client() as client:
        agent = await _first_agent(client)
        resp = await client.post(f"/api/v1/agents/{agent['id']}/test", json={"prompt": ""})
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_duplicate_agent_copies_configuration():
    async with _client() as client:
        agent = await _first_agent(client)
        dup = await client.post(f"/api/v1/agents/{agent['id']}/duplicate")
        assert dup.status_code == 201
        clone = dup.json()
        try:
            assert clone["id"] != agent["id"]
            assert clone["name"].endswith("(copy)")
            assert clone["node_type"] == agent["node_type"]
            assert clone["model_name"] == agent["model_name"]
            assert clone["provider_id"] == agent["provider_id"]
            assert clone["tools_config"] == agent["tools_config"]
        finally:
            await client.delete(f"/api/v1/agents/{clone['id']}")


# --------------------------------------------------------------------------
# Execution retry / delete
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retry_execution_creates_a_new_record():
    async with _client() as client:
        workflows = (await client.get("/api/v1/workflows")).json()
        wf_id = workflows[0]["id"]

        first = await client.post(
            f"/api/v1/workflows/{wf_id}/execute",
            json={"task_prompt": "retry contract test"},
        )
        assert first.status_code == 202
        source = first.json()["id"]

        # Cancel so it reaches a terminal state before retrying.
        await client.post(f"/api/v1/executions/{source}/cancel")

        retried = await client.post(f"/api/v1/executions/{source}/retry")
        assert retried.status_code == 202
        new_exec = retried.json()
        try:
            assert new_exec["id"] != source
            assert new_exec["task_prompt"] == "retry contract test"
            assert new_exec["workflow_id"] == wf_id
        finally:
            await client.post(f"/api/v1/executions/{new_exec['id']}/cancel")


@pytest.mark.asyncio
async def test_retry_active_execution_conflicts():
    async with _client() as client:
        workflows = (await client.get("/api/v1/workflows")).json()
        wf_id = workflows[0]["id"]
        created = await client.post(
            f"/api/v1/workflows/{wf_id}/execute",
            json={"task_prompt": "retry conflict test"},
        )
        exec_id = created.json()["id"]
        try:
            resp = await client.post(f"/api/v1/executions/{exec_id}/retry")
            # Either still running (409) or already finished (202) is possible;
            # a conflict must carry the documented code.
            if resp.status_code == 409:
                assert resp.json()["code"] == "conflict"
            else:
                assert resp.status_code == 202
                await client.post(
                    f"/api/v1/executions/{resp.json()['id']}/cancel"
                )
        finally:
            await client.post(f"/api/v1/executions/{exec_id}/cancel")


@pytest.mark.asyncio
async def test_delete_execution_guards_active_runs():
    async with _client() as client:
        workflows = (await client.get("/api/v1/workflows")).json()
        wf_id = workflows[0]["id"]
        created = await client.post(
            f"/api/v1/workflows/{wf_id}/execute",
            json={"task_prompt": "delete guard test"},
        )
        exec_id = created.json()["id"]

        # While active, deletion is refused.
        active_delete = await client.delete(f"/api/v1/executions/{exec_id}")
        assert active_delete.status_code == 409

        await client.post(f"/api/v1/executions/{exec_id}/cancel")

        # Once terminal it can be removed, and a second delete 404s.
        from app.core.database import AsyncSessionLocal
        from app.models.execution import WorkflowExecution
        import uuid as _uuid

        async with AsyncSessionLocal() as session:
            row = await session.get(WorkflowExecution, _uuid.UUID(exec_id))
            row.status = "cancelled"
            await session.commit()

        assert (await client.delete(f"/api/v1/executions/{exec_id}")).status_code == 204
        assert (await client.delete(f"/api/v1/executions/{exec_id}")).status_code == 404
