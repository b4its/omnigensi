from typing import List, Dict, Any
from fastapi import APIRouter
from app.engine.tool_registry import AVAILABLE_TOOLS_METADATA

router = APIRouter(prefix="/tools", tags=["Hardware & Device Tools"])


@router.get("", response_model=List[Dict[str, Any]])
async def list_available_tools() -> Any:
    """
    Returns all registered hardware interaction and document generator tools.
    """
    return AVAILABLE_TOOLS_METADATA
