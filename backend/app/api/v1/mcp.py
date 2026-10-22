from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from app.engine.mcp_bridge import mcp_manager, MCPServerConfig

router = APIRouter(prefix="/mcp", tags=["Model Context Protocol (MCP)"])

class ToolExecuteRequest(BaseModel):
    arguments: Dict[str, Any] = {}

class MCPServerUpdateRequest(BaseModel):
    """Partial update for an existing MCP server.

    ``name`` is immutable; rename support would have to migrate the tool cache
    and any workflow references, so it is intentionally excluded.
    """

    server_type: Optional[str] = Field(default=None, description="stdio or sse")
    command: Optional[str] = Field(default=None, description="Command for stdio")
    args: Optional[List[str]] = Field(default=None, description="CLI arguments")
    env: Optional[Dict[str, str]] = Field(default=None, description="Environment")
    url: Optional[str] = Field(default=None, description="URL for SSE")
    enabled: Optional[bool] = Field(default=None, description="Enable or disable")
    description: Optional[str] = None

class MCPServerStateRequest(BaseModel):
    """Toggle the enable flag without touching the rest of the config."""

    enabled: bool

class MCPServerToolsResponse(BaseModel):
    """Tools discovered from a single MCP server."""

    server: str
    tools: List[Dict[str, Any]] = []

class MCPToolExecuteResponse(BaseModel):
    """Result of executing one tool on an MCP server.

    The bridge already returns ``{"status": ..., "result"|"message": ...}``, so
    the endpoint passes that through and only guarantees the shape is stable
    for typed clients instead of double-wrapping it.
    """

    status: str = "success"
    result: Any = None
    message: Optional[str] = None


def _require_server(server_name: str) -> MCPServerConfig:
    server = mcp_manager.get_server(server_name)
    if not server:
        raise HTTPException(
            status_code=404, detail=f"MCP server '{server_name}' not found"
        )
    return server


def _validate_transport(config: MCPServerConfig) -> None:
    """Reject configs the bridge cannot actually connect with."""
    if config.server_type not in ("stdio", "sse"):
        raise HTTPException(
            status_code=400,
            detail="server_type must be 'stdio' or 'sse'",
        )
    if config.server_type == "stdio" and not config.command:
        raise HTTPException(
            status_code=400,
            detail="A command is required for stdio transport",
        )
    if config.server_type == "sse" and not config.url:
        raise HTTPException(
            status_code=400, detail="A url is required for sse transport"
        )


@router.get("/servers", response_model=List[MCPServerConfig])
async def list_mcp_servers():
    """
    Returns list of all configured and registered MCP servers.

    Disabled servers are included so clients can re-enable them; inspect the
    ``enabled`` flag before offering tool discovery.
    """
    return mcp_manager.list_servers()


@router.post("/servers", response_model=MCPServerConfig, status_code=status.HTTP_201_CREATED)
async def register_mcp_server(config: MCPServerConfig):
    """
    Registers a new Model Context Protocol (MCP) server.
    """
    if mcp_manager.has_server(config.name):
        raise HTTPException(
            status_code=409,
            detail=f"MCP server '{config.name}' already exists",
        )
    _validate_transport(config)
    mcp_manager.register_server(config)
    return config


@router.put("/servers/{server_name}", response_model=MCPServerConfig)
async def update_mcp_server(server_name: str, payload: MCPServerUpdateRequest):
    """
    Replaces the configuration of an existing MCP server.

    Only the provided fields change. Changing the transport drops previously
    discovered tools so they are re-read from the new endpoint.
    """
    current = _require_server(server_name)
    merged = current.model_copy(
        update={k: v for k, v in payload.model_dump(exclude_none=True).items()}
    )
    _validate_transport(merged)
    return mcp_manager.update_server(server_name, merged)


@router.patch("/servers/{server_name}", response_model=MCPServerConfig)
async def toggle_mcp_server(server_name: str, payload: MCPServerStateRequest):
    """
    Enables or disables an MCP server without removing its configuration.

    Disabled servers refuse tool discovery and execution with a 409.
    """
    _require_server(server_name)
    return mcp_manager.set_enabled(server_name, payload.enabled)


@router.delete(
    "/servers/{server_name}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_mcp_server(server_name: str) -> None:
    """
    Removes an MCP server and its cached tools.

    Note that MCP registrations are held in memory, so this change is lost on
    backend restart.
    """
    _require_server(server_name)
    mcp_manager.unregister_server(server_name)


@router.get("/servers/{server_name}/tools", response_model=MCPServerToolsResponse)
async def list_mcp_server_tools(server_name: str):
    """
    Discovers available tools from the specified MCP server.
    """
    server = _require_server(server_name)
    if not server.enabled:
        raise HTTPException(
            status_code=409,
            detail=f"MCP server '{server_name}' is disabled",
        )

    tools = await mcp_manager.list_tools_for_server(server_name)
    return MCPServerToolsResponse(server=server_name, tools=tools)


@router.post(
    "/servers/{server_name}/tools/{tool_name}/execute",
    response_model=MCPToolExecuteResponse,
)
async def execute_mcp_tool(server_name: str, tool_name: str, payload: ToolExecuteRequest):
    """
    Executes a specific tool on an MCP server.
    """
    server = _require_server(server_name)
    if not server.enabled:
        raise HTTPException(
            status_code=409,
            detail=f"MCP server '{server_name}' is disabled",
        )

    try:
        result = await mcp_manager.execute_tool(server_name, tool_name, payload.arguments)
        if not isinstance(result, dict):
            return MCPToolExecuteResponse(status="success", result=result)

        # Preserve the whole bridge payload: it may carry diagnostics such as
        # `tool_available: false` that the caller must not lose.
        return MCPToolExecuteResponse(
            status=str(result.get("status", "success")),
            result=result if "result" not in result else result.get("result"),
            message=result.get("message"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
