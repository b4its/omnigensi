"""Tests for graph validation, duplication and execution lifecycle."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.engine.graph_validation import validate_graph
from app.main import app


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _first_agent_id(client: AsyncClient) -> str:
    agents = (await client.get("/api/v1/agents?limit=1")).json()
    assert agents, "test suite expects at least one seeded agent"
    return agents[0]["id"]


def _valid_graph(agent_id: str) -> dict:
    return {
        "entry_point": "n1",
        "nodes": [{"node_id": "n1", "agent_id": agent_id}],
        "edges": [{"from": "n1", "to": "END", "type": "normal"}],
    }


# --------------------------------------------------------------------------
# Pure validator
# --------------------------------------------------------------------------

def test_validator_accepts_valid_graph():
    result = validate_graph(
        {
            "entry_point": "a",
            "nodes": [{"node_id": "a", "agent_id": "00000000-0000-0000-0000-000000000001"}],
            "edges": [{"from": "a", "to": "END"}],
        }
    )
    assert result.valid is True
    assert result.node_count == 1
    assert result.edge_count == 1
    assert result.entry_point == "a"


def test_validator_flags_empty_graph():
    result = validate_graph({"nodes": [], "edges": []})
    assert result.valid is False
    assert any(i.code == "empty_graph" for i in result.issues)


def test_validator_flags_missing_and_invalid_fields():
    result = validate_graph(
        {
            "nodes": [
                {"agent_id": "00000000-0000-0000-0000-000000000001"},  # no node_id
                {"node_id": "b"},  # no agent_id
                {"node_id": "c", "agent_id": "not-a-uuid"},
            ],
            "edges": [],
        }
    )
    codes = {i.code for i in result.issues}
    assert "missing_node_id" in codes
    assert "missing_agent_id" in codes
    assert "invalid_agent_id" in codes


def test_validator_flags_duplicate_node_ids():
    agent = "00000000-0000-0000-0000-000000000001"
    result = validate_graph(
        {
            "nodes": [
                {"node_id": "dup", "agent_id": agent},
                {"node_id": "dup", "agent_id": agent},
            ],
            "edges": [],
        }
    )
    assert any(i.code == "duplicate_node_id" for i in result.issues)


def test_validator_flags_unknown_edge_targets():
    agent = "00000000-0000-0000-0000-000000000001"
    result = validate_graph(
        {
            "nodes": [{"node_id": "a", "agent_id": agent}],
            "edges": [
                {"from": "a", "to": "ghost", "type": "normal"},
                {"from": "phantom", "to": "END"},
            ],
        }
    )
    codes = {i.code for i in result.issues}
    assert "unknown_edge_target" in codes
    assert "unknown_edge_source" in codes


def test_validator_flags_conditional_targets():
    agent = "00000000-0000-0000-0000-000000000001"
    result = validate_graph(
        {
            "nodes": [{"node_id": "a", "agent_id": agent}],
            "edges": [
                {"from": "a", "type": "conditional", "on_approve": "END", "on_reject": "ghost"}
            ],
        }
    )
    assert any(i.code == "unknown_edge_target" for i in result.issues)


def test_validator_flags_unknown_agent_when_list_supplied():
    known = {"00000000-0000-0000-0000-000000000001"}
    result = validate_graph(
        {
            "nodes": [
                {"node_id": "a", "agent_id": "00000000-0000-0000-0000-000000000009"}
            ],
            "edges": [],
        },
        known_agent_ids=known,
    )
    assert any(i.code == "unknown_agent" for i in result.issues)


def test_validator_flags_bad_entry_point():
    agent = "00000000-0000-0000-0000-000000000001"
    result = validate_graph(
        {
            "entry_point": "nope",
            "nodes": [{"node_id": "a", "agent_id": agent}],
            "edges": [],
        }
    )
    assert any(i.code == "unknown_entry_point" for i in result.issues)
    # Falls back to the first node so the rest of the report is still useful
    assert result.entry_point == "a"


# --------------------------------------------------------------------------
# API: save is guarded, dry-run is available
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_workflow_rejects_invalid_graph():
    async with _client() as client:
        resp = await client.post(
            "/api/v1/workflows",
            json={"name": "bad-graph", "graph_schema": {"nonsense": True}},
        )
        assert resp.status_code == 400
        assert resp.json()["code"] == "bad_request"


@pytest.mark.asyncio
async def test_create_workflow_accepts_valid_graph_and_can_be_deleted():
    async with _client() as client:
        agent_id = await _first_agent_id(client)
        resp = await client.post(
            "/api/v1/workflows",
            json={"name": "validation-ok", "graph_schema": _valid_graph(agent_id)},
        )
        assert resp.status_code == 201, resp.text
        wf_id = resp.json()["id"]
        try:
            check = await client.get(f"/api/v1/workflows/{wf_id}/validate")
            assert check.status_code == 200
            assert check.json()["valid"] is True
        finally:
            await client.delete(f"/api/v1/workflows/{wf_id}")


@pytest.mark.asyncio
async def test_update_workflow_rejects_invalid_graph():
    async with _client() as client:
        agent_id = await _first_agent_id(client)
        created = await client.post(
            "/api/v1/workflows",
            json={"name": "update-guard", "graph_schema": _valid_graph(agent_id)},
        )
        wf_id = created.json()["id"]
        try:
            resp = await client.put(
                f"/api/v1/workflows/{wf_id}",
                json={"graph_schema": {"nodes": []}},
            )
            assert resp.status_code == 400
        finally:
            await client.delete(f"/api/v1/workflows/{wf_id}")


@pytest.mark.asyncio
async def test_validate_endpoint_returns_every_issue():
    async with _client() as client:
        resp = await client.post(
            "/api/v1/workflows/validate",
            json={
                "name": "multi-issue",
                "graph_schema": {
                    "nodes": [{"node_id": "a"}],
                    "edges": [{"from": "a", "to": "ghost"}],
                },
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is False
        codes = {i["code"] for i in body["issues"]}
        assert "missing_agent_id" in codes
        assert "unknown_edge_target" in codes


@pytest.mark.asyncio
async def test_duplicate_workflow_copies_graph():
    async with _client() as client:
        agent_id = await _first_agent_id(client)
        created = await client.post(
            "/api/v1/workflows",
            json={"name": "clone-source", "graph_schema": _valid_graph(agent_id)},
        )
        source = created.json()
        clone_id = None
        try:
            dup = await client.post(f"/api/v1/workflows/{source['id']}/duplicate")
            assert dup.status_code == 201
            clone = dup.json()
            clone_id = clone["id"]
            assert clone["id"] != source["id"]
            assert clone["name"].endswith("(copy)")
            assert clone["graph_schema"] == source["graph_schema"]
        finally:
            await client.delete(f"/api/v1/workflows/{source['id']}")
            if clone_id:
                await client.delete(f"/api/v1/workflows/{clone_id}")


@pytest.mark.asyncio
async def test_workflow_search_filter():
    async with _client() as client:
        resp = await client.get("/api/v1/workflows?q=zzz-no-such-name")
        assert resp.status_code == 200
        assert resp.json() == []
        assert resp.headers["x-total-count"] == "0"


@pytest.mark.asyncio
async def test_validating_unknown_workflow_404():
    async with _client() as client:
        resp = await client.get(
            "/api/v1/workflows/00000000-0000-0000-0000-000000000000/validate"
        )
        assert resp.status_code == 404
