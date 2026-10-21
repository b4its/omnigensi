"""Hardware & device tools: discovery and standalone execution."""

import inspect
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.engine.tool_registry import AVAILABLE_TOOLS_METADATA, DEVICE_TOOL_MAP

router = APIRouter(prefix="/tools", tags=["Hardware & Device Tools"])


class ToolMetadata(BaseModel):
    """A tool an agent can be granted."""

    id: str
    name: str
    description: str
    icon: Optional[str] = None
    category: Optional[str] = None
    extension: Optional[str] = None
    requires_write: bool = False
    parameters: List[str] = Field(
        default_factory=list,
        description="Accepted argument names, so clients can build a form",
    )


class ToolExecuteRequest(BaseModel):
    """Arguments passed to a tool."""

    arguments: Dict[str, Any] = Field(default_factory=dict)


class ToolExecuteResponse(BaseModel):
    """Result of a standalone tool run."""

    ok: bool
    tool_id: str
    result: Any = None
    error: Optional[str] = None


def _parameters_for(tool_id: str) -> List[str]:
    """Argument names accepted by a tool.

    Registry entries are LangChain ``StructuredTool`` objects, so the shape
    comes from ``args_schema`` rather than the underlying callable.
    """
    tool = DEVICE_TOOL_MAP.get(tool_id)
    if tool is None:
        return []

    schema = getattr(tool, "args_schema", None)
    model_fields = getattr(schema, "model_fields", None)
    if isinstance(model_fields, dict):
        return list(model_fields.keys())

    target = getattr(tool, "func", tool)
    try:
        signature = inspect.signature(target)
    except (TypeError, ValueError):
        return []
    return [
        name
        for name, param in signature.parameters.items()
        if param.kind
        in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    ]


def _metadata_with_parameters() -> List[ToolMetadata]:
    tools: List[ToolMetadata] = []
    for entry in AVAILABLE_TOOLS_METADATA:
        tools.append(
            ToolMetadata(
                id=entry["id"],
                name=entry.get("name", entry["id"]),
                description=entry.get("description", ""),
                icon=entry.get("icon"),
                category=entry.get("category"),
                extension=entry.get("extension"),
                requires_write=bool(entry.get("requires_write", False)),
                parameters=_parameters_for(entry["id"]),
            )
        )
    return tools


@router.get("", response_model=List[ToolMetadata])
async def list_available_tools() -> Any:
    """Registered hardware interaction and document generator tools.

    Includes each tool's accepted parameter names so a client can render an
    argument form without hardcoding the registry.
    """
    return _metadata_with_parameters()


@router.post("/{tool_id}/execute", response_model=ToolExecuteResponse)
async def execute_tool(tool_id: str, payload: ToolExecuteRequest) -> Any:
    """Runs a single tool outside a workflow.

    Useful to verify the workspace bridge (e.g. that a PDF can actually be
    written) before wiring the tool into an agent.
    """
    tool = DEVICE_TOOL_MAP.get(tool_id)
    if tool is None:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")

    accepted = set(_parameters_for(tool_id))
    unknown = set(payload.arguments) - accepted
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown argument(s) for '{tool_id}': {', '.join(sorted(unknown))}. "
                f"Accepted: {', '.join(sorted(accepted)) or 'none'}"
            ),
        )

    try:
        # StructuredTool exposes both a sync and an async entry point.
        runner = getattr(tool, "ainvoke", None)
        if runner is not None:
            result = await runner(payload.arguments)
        else:
            result = tool(**payload.arguments)
            if inspect.isawaitable(result):
                result = await result
        return ToolExecuteResponse(ok=True, tool_id=tool_id, result=result)
    except TypeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 - surfaced to the operator
        return ToolExecuteResponse(ok=False, tool_id=tool_id, error=str(exc))
