import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.engine.mcp_bridge import mcp_manager, MCPServerConfig
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_mcp_manager_servers_and_tools():
    servers = mcp_manager.list_servers()
    assert len(servers) >= 2
    server_names = [s.name for s in servers]
    assert "filesystem-mcp" in server_names

    # Test tools discovery for filesystem-mcp
    tools = await mcp_manager.list_tools_for_server("filesystem-mcp")
    assert len(tools) > 0
    tool_names = [t["name"] for t in tools]
    assert any("read" in name for name in tool_names)

    # Test tool wrapping to LangChain StructuredTool
    read_tool_def = next(t for t in tools if "read" in t["name"])
    lc_tool = mcp_manager.create_langchain_tool("filesystem-mcp", read_tool_def)
    assert "read" in lc_tool.name

    # Test direct execution of MCP tool
    exec_res = await mcp_manager.execute_tool(
        "filesystem-mcp", "mcp_read_file", {"path": "non_existent_file.txt"}
    )
    assert exec_res["status"] in ("success", "error")


@pytest.mark.asyncio
async def test_mcp_api_endpoints():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(),
    ) as client:
        # GET /api/v1/mcp/servers
        res = await client.get("/api/v1/mcp/servers")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        assert len(data) >= 2

        # POST /api/v1/mcp/servers (register a custom server)
        new_server = {
            "name": "test-custom-mcp",
            "server_type": "stdio",
            "command": "python",
            "args": ["-c", "print('hello')"],
            "description": "Test MCP server",
            "enabled": True,
        }
        create_res = await client.post("/api/v1/mcp/servers", json=new_server)
        assert create_res.status_code == 201

        # GET /api/v1/mcp/servers/test-custom-mcp/tools
        tools_res = await client.get("/api/v1/mcp/servers/test-custom-mcp/tools")
        assert tools_res.status_code == 200
        assert "tools" in tools_res.json()

        # POST execute
        exec_res = await client.post(
            "/api/v1/mcp/servers/test-custom-mcp/tools/mcp_test-custom-mcp_query/execute",
            json={"arguments": {"query": "status"}},
        )
        assert exec_res.status_code == 200
        assert exec_res.json()["status"] == "success"
