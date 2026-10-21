"""Contract tests for the mobile/web parity features.

Covers the bootstrap config endpoint, pagination, the uniform error
envelope and CORS behaviour that both clients depend on.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import DEFAULT_LIMIT, MAX_LIMIT
from app.main import STREAM_EVENTS, app


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_client_config_bootstrap():
    """A mobile client must be able to discover the API contract at startup."""
    async with _client() as client:
        resp = await client.get("/api/v1/config")
        assert resp.status_code == 200
        data = resp.json()

        assert data["service"] == "omnigensi-backend"
        assert data["api_version"] == "v1"
        assert data["api_base_path"] == "/api/v1"
        assert data["base_url"].startswith("http")

        # Stream contract
        streaming = data["streaming"]
        assert streaming["content_type"] == "text/event-stream"
        assert "{execution_id}" in streaming["path_template"]
        assert set(streaming["events"]) == set(STREAM_EVENTS)

        # Feature flags must match what the backend actually exposes
        features = data["features"]
        assert features["providers"] is True
        assert features["agents"] is True
        assert features["workflows"] is True
        assert features["execution_streaming"] is True
        assert features["execution_cancel"] is True
        assert features["tool_approval"] is True
        assert features["mcp_servers"] is True
        assert features["file_download"] is True
        assert features["file_upload"] is False

        assert data["pagination"]["default_limit"] == DEFAULT_LIMIT
        assert data["pagination"]["max_limit"] == MAX_LIMIT


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    ["/api/v1/providers", "/api/v1/agents", "/api/v1/workflows", "/api/v1/executions"],
)
async def test_list_endpoints_are_paginated(path: str):
    """Collections must honour limit/offset and report totals via headers."""
    async with _client() as client:
        resp = await client.get(f"{path}?limit=1&offset=0")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) <= 1

        assert resp.headers["x-limit"] == "1"
        assert resp.headers["x-offset"] == "0"
        total = int(resp.headers["x-total-count"])
        assert total >= len(resp.json())


@pytest.mark.asyncio
async def test_pagination_offset_skips_items():
    """Offset must advance through a stable ordering."""
    async with _client() as client:
        first = await client.get("/api/v1/agents?limit=1&offset=0")
        second = await client.get("/api/v1/agents?limit=1&offset=1")
        assert first.status_code == second.status_code == 200
        if int(first.headers["x-total-count"]) >= 2:
            assert first.json()[0]["id"] != second.json()[0]["id"]


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", [0, -5, MAX_LIMIT + 1])
async def test_pagination_rejects_invalid_limit(limit: int):
    async with _client() as client:
        resp = await client.get(f"/api/v1/agents?limit={limit}")
        assert resp.status_code == 422
        assert resp.json()["code"] == "validation_error"


@pytest.mark.asyncio
async def test_not_found_uses_uniform_envelope():
    """detail must always be a string so mobile clients never branch on type."""
    async with _client() as client:
        resp = await client.get("/api/v1/agents/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404
        body = resp.json()
        assert body["success"] is False
        assert isinstance(body["detail"], str)
        assert body["code"] == "not_found"
        assert body["request_id"]
        assert resp.headers["x-request-id"] == body["request_id"]


@pytest.mark.asyncio
async def test_validation_error_uses_uniform_envelope():
    async with _client() as client:
        resp = await client.post("/api/v1/agents", json={"name": "incomplete"})
        assert resp.status_code == 422
        body = resp.json()
        assert isinstance(body["detail"], str)
        assert body["code"] == "validation_error"
        assert isinstance(body["errors"], list) and body["errors"]
        assert {"loc", "msg", "type"} <= set(body["errors"][0])


@pytest.mark.asyncio
async def test_health_is_typed_and_versioned():
    async with _client() as client:
        for path in ("/health", "/api/v1/health"):
            resp = await client.get(path)
            assert resp.status_code == 200
            data = resp.json()
            assert set(data) == {"status", "service", "version", "workspace_root"}


@pytest.mark.asyncio
async def test_action_endpoints_are_typed():
    """approve-tool/cancel previously returned an untyped dict."""
    async with _client() as client:
        wf = (await client.get("/api/v1/workflows")).json()[0]
        exec_resp = await client.post(
            f"/api/v1/workflows/{wf['id']}/execute",
            json={"task_prompt": "contract test"},
        )
        assert exec_resp.status_code == 202
        exec_id = exec_resp.json()["id"]

        cancel = await client.post(f"/api/v1/executions/{exec_id}/cancel")
        assert cancel.status_code == 200
        body = cancel.json()
        assert {"success", "status", "message"} <= set(body)
        assert body["success"] is True


@pytest.mark.asyncio
async def test_mcp_tools_response_is_typed():
    async with _client() as client:
        servers = (await client.get("/api/v1/mcp/servers")).json()
        assert servers
        name = servers[0]["name"]
        resp = await client.get(f"/api/v1/mcp/servers/{name}/tools")
        assert resp.status_code == 200
        body = resp.json()
        assert body["server"] == name
        assert isinstance(body["tools"], list)


@pytest.mark.asyncio
async def test_cors_allows_lan_origin_and_rejects_unknown():
    """The web UI opened from a phone on the LAN must be allowed."""
    async with _client() as client:
        allowed = await client.options(
            "/api/v1/agents",
            headers={
                "Origin": "http://192.168.1.10:5296",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert allowed.headers.get("access-control-allow-origin") == "http://192.168.1.10:5296"

        blocked = await client.options(
            "/api/v1/agents",
            headers={
                "Origin": "http://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" not in blocked.headers


@pytest.mark.asyncio
async def test_provider_update_preserves_api_key_when_omitted():
    """Editing a provider without sending api_key must keep the stored key."""
    async with _client() as client:
        created = await client.post(
            "/api/v1/providers",
            json={
                "name": "Contract Test Provider",
                "provider_type": "custom",
                "base_url": "http://localhost:9999",
                "api_key": "sk-secret-contract-test",
                "is_active": True,
            },
        )
        assert created.status_code == 201
        provider_id = created.json()["id"]
        assert created.json()["has_api_key"] is True

        renamed = await client.put(
            f"/api/v1/providers/{provider_id}",
            json={"name": "Contract Test Provider Renamed"},
        )
        assert renamed.status_code == 200
        assert renamed.json()["name"] == "Contract Test Provider Renamed"
        assert renamed.json()["has_api_key"] is True

        deleted = await client.delete(f"/api/v1/providers/{provider_id}")
        assert deleted.status_code == 204


@pytest.mark.asyncio
async def test_mcp_execute_preserves_bridge_status_field():
    """The typed wrapper must pass the bridge's own status through, not rewrap it."""
    async with _client() as client:
        servers = (await client.get("/api/v1/mcp/servers")).json()
        name = servers[0]["name"]

        resp = await client.post(
            f"/api/v1/mcp/servers/{name}/tools/mcp_read_file/execute",
            json={"arguments": {"path": "definitely_missing_file.txt"}},
        )
        assert resp.status_code == 200
        body = resp.json()
        # Flat contract: the outer status is always present at the root and the
        # bridge payload is passed through untouched under `result`.
        assert body["status"] in ("success", "error")
        assert set(body) <= {"status", "result", "message"}
        result = body.get("result")
        assert result is None or isinstance(result, dict)


@pytest.mark.asyncio
async def test_file_download_accepts_relative_and_absolute_paths():
    """Mobile clients download by either `filename` or the tool's `filepath`."""
    from pathlib import Path

    from app.core.config import settings

    target = settings.workspace_path / "mobile_parity_download_probe.md"
    target.write_text("# probe\n", encoding="utf-8")
    try:
        async with _client() as client:
            relative = await client.get("/api/v1/files/mobile_parity_download_probe.md")
            assert relative.status_code == 200
            assert relative.content == b"# probe\n"
            assert "text/markdown" in relative.headers["content-type"]

            absolute = await client.get(
                f"/api/v1/files/{target.as_posix()}"
            )
            assert absolute.status_code == 200
            assert absolute.content == b"# probe\n"
    finally:
        Path(target).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_file_download_rejects_traversal():
    async with _client() as client:
        resp = await client.get("/api/v1/files/..%2F..%2Fetc%2Fpasswd")
        assert resp.status_code == 400
        assert resp.json()["code"] == "bad_request"


@pytest.mark.asyncio
async def test_sanitize_workspace_path_blocks_sibling_prefix(tmp_path, monkeypatch):
    """A sibling dir sharing the workspace prefix must not pass the check."""
    from app.core import security

    workspace = tmp_path / "workspace"
    sibling = tmp_path / "workspace-evil"
    workspace.mkdir()
    sibling.mkdir()
    (sibling / "secret.txt").write_text("nope")

    monkeypatch.setattr(
        type(security.settings),
        "workspace_path",
        property(lambda self: workspace),
    )

    with pytest.raises(ValueError):
        security.sanitize_workspace_path(str(sibling / "secret.txt"))


# ---------------------------------------------------------------------------
# MCP server management (add / remove / toggle / edit)
# ---------------------------------------------------------------------------

def _mcp_payload(name: str = "contract-mcp", **overrides):
    payload = {
        "name": name,
        "server_type": "stdio",
        "command": "python",
        "args": ["-c", "print(1)"],
        "description": "contract test server",
        "enabled": True,
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_mcp_server_full_lifecycle():
    """Add -> toggle -> edit -> remove, verifying each step's state."""
    name = "lifecycle-mcp"
    async with _client() as client:
        try:
            # ADD
            created = await client.post("/api/v1/mcp/servers", json=_mcp_payload(name))
            assert created.status_code == 201
            assert created.json()["name"] == name
            assert created.json()["enabled"] is True

            names = [s["name"] for s in (await client.get("/api/v1/mcp/servers")).json()]
            assert name in names

            # DUPLICATE -> 409
            duplicate = await client.post("/api/v1/mcp/servers", json=_mcp_payload(name))
            assert duplicate.status_code == 409
            assert duplicate.json()["code"] == "conflict"

            # DISABLE
            off = await client.patch(
                f"/api/v1/mcp/servers/{name}", json={"enabled": False}
            )
            assert off.status_code == 200
            assert off.json()["enabled"] is False

            # Disabled servers refuse discovery and execution
            assert (
                await client.get(f"/api/v1/mcp/servers/{name}/tools")
            ).status_code == 409
            assert (
                await client.post(
                    f"/api/v1/mcp/servers/{name}/tools/whatever/execute",
                    json={"arguments": {}},
                )
            ).status_code == 409

            # RE-ENABLE
            on = await client.patch(
                f"/api/v1/mcp/servers/{name}", json={"enabled": True}
            )
            assert on.json()["enabled"] is True

            # EDIT (partial: only description changes)
            edited = await client.put(
                f"/api/v1/mcp/servers/{name}", json={"description": "edited server"}
            )
            assert edited.status_code == 200
            assert edited.json()["description"] == "edited server"
            assert edited.json()["command"] == "python"
            assert edited.json()["args"] == ["-c", "print(1)"]

            # REMOVE
            removed = await client.delete(f"/api/v1/mcp/servers/{name}")
            assert removed.status_code == 204
            names = [s["name"] for s in (await client.get("/api/v1/mcp/servers")).json()]
            assert name not in names

            # REMOVE again -> 404
            again = await client.delete(f"/api/v1/mcp/servers/{name}")
            assert again.status_code == 404
            assert again.json()["code"] == "not_found"
        finally:
            await client.delete(f"/api/v1/mcp/servers/{name}")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload, detail_fragment",
    [
        ({"name": "no-command", "server_type": "stdio"}, "command is required"),
        ({"name": "no-url", "server_type": "sse"}, "url is required"),
        ({"name": "bad-type", "server_type": "carrier-pigeon"}, "stdio' or 'sse"),
    ],
)
async def test_mcp_server_rejects_invalid_transport(payload, detail_fragment):
    async with _client() as client:
        resp = await client.post("/api/v1/mcp/servers", json=payload)
        assert resp.status_code == 400
        assert detail_fragment in resp.json()["detail"]
        # Nothing must have been persisted on failure
        names = [s["name"] for s in (await client.get("/api/v1/mcp/servers")).json()]
        assert payload["name"] not in names


@pytest.mark.asyncio
async def test_mcp_update_can_switch_transport():
    """Switching stdio -> sse must invalidate the previously cached tools."""
    name = "transport-switch-mcp"
    async with _client() as client:
        try:
            await client.post("/api/v1/mcp/servers", json=_mcp_payload(name))
            # Prime the tool cache
            await client.get(f"/api/v1/mcp/servers/{name}/tools")

            switched = await client.put(
                f"/api/v1/mcp/servers/{name}",
                json={
                    "server_type": "sse",
                    "url": "http://localhost:9000/sse",
                    "command": None,
                    "args": [],
                },
            )
            assert switched.status_code == 200
            body = switched.json()
            assert body["server_type"] == "sse"
            assert body["url"] == "http://localhost:9000/sse"

            # The server must still be usable after the transport change
            assert (
                await client.get(f"/api/v1/mcp/servers/{name}/tools")
            ).status_code == 200
        finally:
            await client.delete(f"/api/v1/mcp/servers/{name}")


@pytest.mark.asyncio
async def test_mcp_remove_does_not_touch_seed_servers():
    """Removing a user server must leave the built-in bridges intact."""
    async with _client() as client:
        await client.post("/api/v1/mcp/servers", json=_mcp_payload("temp-mcp"))
        assert (await client.delete("/api/v1/mcp/servers/temp-mcp")).status_code == 204

        names = [s["name"] for s in (await client.get("/api/v1/mcp/servers")).json()]
        assert "filesystem-mcp" in names
        assert "memory-mcp" in names


def test_mcp_manager_unregister_invalidates_cache():
    """The manager must drop cached tools when a server disappears."""
    from app.engine.mcp_bridge import MCPBridgeManager, MCPServerConfig

    manager = MCPBridgeManager()
    manager.register_server(
        MCPServerConfig(name="cache-probe", server_type="stdio", command="echo")
    )
    manager._tools_cache["cache-probe"] = [{"name": "probe:tool"}]
    manager._langchain_tools["cache-probe:tool"] = object()

    assert manager.unregister_server("cache-probe") is True
    assert manager.get_server("cache-probe") is None
    assert "cache-probe" not in manager._tools_cache
    assert "cache-probe:tool" not in manager._langchain_tools

    # Unregistering an unknown server is a no-op, not an error
    assert manager.unregister_server("cache-probe") is False


# ---------------------------------------------------------------------------
# Dashboard stats, execution filters and provider connection testing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stats_endpoint_aggregates_everything():
    """The dashboard must not have to page collections to count them."""
    async with _client() as client:
        resp = await client.get("/api/v1/stats")
        assert resp.status_code == 200
        data = resp.json()

        assert set(data) == {
            "providers",
            "providers_active",
            "agents",
            "workflows",
            "executions",
            "total_tokens",
            "estimated_cost_usd",
            "mcp_servers",
            "mcp_servers_enabled",
            "tools_available",
            "generated_at",
        }

        # Counts must agree with the collection totals reported in headers.
        for key, path in (
            ("providers", "/api/v1/providers"),
            ("agents", "/api/v1/agents"),
            ("workflows", "/api/v1/workflows"),
        ):
            listing = await client.get(f"{path}?limit=1")
            assert data[key] == int(listing.headers["x-total-count"]), key

        breakdown = data["executions"]
        assert breakdown["total"] >= 1
        assert breakdown["total"] == (
            breakdown["completed"]
            + breakdown["failed"]
            + breakdown["running"]
            + breakdown["pending"]
            + breakdown["waiting_approval"]
            + breakdown["cancelled"]
        )
        assert data["tools_available"] >= 5
        assert data["mcp_servers"] >= 2


@pytest.mark.asyncio
async def test_stats_counts_active_providers():
    async with _client() as client:
        before = (await client.get("/api/v1/stats")).json()

        created = await client.post(
            "/api/v1/providers",
            json={
                "name": "stats-inactive-probe",
                "provider_type": "custom",
                "base_url": "http://localhost:9999",
                "api_key": "",
                "is_active": False,
            },
        )
        provider_id = created.json()["id"]
        try:
            after = (await client.get("/api/v1/stats")).json()
            assert after["providers"] == before["providers"] + 1
            assert after["providers_active"] == before["providers_active"]
        finally:
            await client.delete(f"/api/v1/providers/{provider_id}")


@pytest.mark.asyncio
async def test_execution_filters_by_status_and_workflow():
    async with _client() as client:
        all_resp = await client.get("/api/v1/executions?limit=1")
        total_all = int(all_resp.headers["x-total-count"])

        completed = await client.get("/api/v1/executions?status=completed&limit=1")
        cancelled = await client.get("/api/v1/executions?status=cancelled&limit=1")
        assert completed.status_code == 200
        assert cancelled.status_code == 200

        total_completed = int(completed.headers["x-total-count"])
        total_cancelled = int(cancelled.headers["x-total-count"])
        # Filters must narrow the total, never inflate it.
        assert total_completed <= total_all
        assert total_cancelled <= total_all

        # Returned rows must actually match the filter.
        for row in (await client.get("/api/v1/executions?status=completed&limit=5")).json():
            assert row["status"] == "completed"

        wf = (await client.get("/api/v1/workflows")).json()[0]
        by_workflow = await client.get(
            f"/api/v1/executions?workflow_id={wf['id']}&limit=5"
        )
        assert by_workflow.status_code == 200
        for row in by_workflow.json():
            assert row["workflow_id"] == wf["id"]


@pytest.mark.asyncio
async def test_execution_filter_rejects_bad_workflow_id():
    async with _client() as client:
        resp = await client.get("/api/v1/executions?workflow_id=not-a-uuid")
        assert resp.status_code == 422
        assert resp.json()["code"] == "validation_error"


@pytest.mark.asyncio
async def test_provider_test_reports_failure_instead_of_faking_success():
    """GET /models falls back to canned data; /test must tell the truth."""
    async with _client() as client:
        created = await client.post(
            "/api/v1/providers",
            json={
                "name": "unreachable-probe",
                "provider_type": "custom",
                "base_url": "http://127.0.0.1:9",
                "api_key": "sk-invalid",
                "is_active": True,
            },
        )
        provider_id = created.json()["id"]
        try:
            # /models lies: always 200 with fallback entries
            models = await client.get(f"/api/v1/providers/{provider_id}/models")
            assert models.status_code == 200
            assert len(models.json()) > 0

            # /test tells the truth
            tested = await client.post(f"/api/v1/providers/{provider_id}/test")
            assert tested.status_code == 200
            body = tested.json()
            assert body["ok"] is False
            assert body["error"]
            assert body["model_count"] == 0
        finally:
            await client.delete(f"/api/v1/providers/{provider_id}")


@pytest.mark.asyncio
async def test_provider_test_unknown_provider_404():
    async with _client() as client:
        resp = await client.post(
            "/api/v1/providers/00000000-0000-0000-0000-000000000000/test"
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cors_exposes_pagination_headers():
    """WebView clients cannot read X-Total-Count unless CORS exposes it."""
    async with _client() as client:
        # expose-headers is only sent on the actual (non-preflight) response.
        resp = await client.get(
            "/api/v1/agents?limit=1",
            headers={"Origin": "http://192.168.1.10:5296"},
        )
        assert resp.status_code == 200
        assert resp.headers["access-control-allow-origin"] == "http://192.168.1.10:5296"
        exposed = resp.headers.get("access-control-expose-headers", "").lower()
        for header in ("x-total-count", "x-limit", "x-offset", "x-request-id"):
            assert header in exposed, header
