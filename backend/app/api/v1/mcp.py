from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from app.engine.mcp_bridge import mcp_manager, MCPServerConfig

router = APIRouter(prefix="/mcp", tags=["Model Context Protocol (MCP)"])


class ToolExecuteRequest(BaseModel):
    arguments: Dict[str, Any] = {}


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


@router.get("/servers", response_model=List[MCPServerConfig])
async def list_mcp_servers():
    """
    Returns list of all configured and registered MCP servers.
    """
    return mcp_manager.list_servers()


@router.post("/servers", response_model=MCPServerConfig, status_code=status.HTTP_201_CREATED)
async def register_mcp_server(config: MCPServerConfig):
    """
    Registers a new Model Context Protocol (MCP) server.
    """
    mcp_manager.register_server(config)
    return config


@router.get("/servers/{server_name}/tools", response_model=MCPServerToolsResponse)
async def list_mcp_server_tools(server_name: str):
    """
    Discovers available tools from the specified MCP server.
    """
    server = mcp_manager.get_server(server_name)
    if not server:
        raise HTTPException(status_code=404, detail=f"MCP server '{server_name}' not found")
    
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
    server = mcp_manager.get_server(server_name)
    if not server:
        raise HTTPException(status_code=404, detail=f"MCP server '{server_name}' not found")

    try:
        result = await mcp_manager.execute_tool(server_name, tool_name, payload.arguments)
        if not isinstance(result, dict):
            return MCPToolExecuteResponse(status="success", result=result)
        return MCPToolExecuteResponse(
            status=str(result.get("status", "success")),
            result=result.get("result"),
            message=result.get("message"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
