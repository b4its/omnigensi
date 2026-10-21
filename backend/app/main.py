import logging
import mimetypes
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.database import init_db
from app.core.errors import install_error_handlers
from app.core.security import sanitize_workspace_path
from app.api.v1.providers import router as providers_router
from app.api.v1.agents import router as agents_router
from app.api.v1.workflows import router as workflows_router
from app.schemas.execution import ExecutionResponse
from app.schemas.system import (
    ClientConfigResponse,
    HealthResponse,
    WorkflowExecutionCreated,
)
from app.api.v1.executions import router as executions_router, trigger_workflow_execution
from app.api.v1.tools import router as tools_router
from app.api.v1.mcp import router as mcp_router
from app.api.v1.stats import router as stats_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("omnigensi")

# SSE event names emitted by the execution engine. Shared with mobile clients
# so they can wire up listeners without reading backend source.
STREAM_EVENTS = [
    "connected",
    "agent_start",
    "token_chunk",
    "review_result",
    "supervisor_directive",
    "device_approval_required",
    "device_file_write",
    "tool_approval_response",
    "workflow_complete",
    "workflow_failed",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Omnigensi backend...")
    # Ensure database schema exists
    await init_db()
    # Ensure workspace directory exists
    settings.workspace_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Workspace directory ready at {settings.workspace_path}")
    yield
    logger.info("Omnigensi backend shutting down.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.APP_VERSION,
    description="Dynamic Multi-Agent AIaaS Platform with Local Device & Hardware Bridge",
    lifespan=lifespan,
)

install_error_handlers(app)

# CORS Middleware - driven by configuration so the same backend serves the web
# UI (browser) and a mobile app / mobile WebView on the LAN.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Pagination metadata lives in headers, so CORS clients (browser and
    # mobile WebViews) must be explicitly allowed to read them.
    expose_headers=[
        "X-Request-ID",
        "Content-Disposition",
        "X-Total-Count",
        "X-Limit",
        "X-Offset",
    ],
    max_age=600,
)

# Register API v1 Routers
app.include_router(providers_router, prefix=settings.API_V1_STR)
app.include_router(agents_router, prefix=settings.API_V1_STR)
app.include_router(workflows_router, prefix=settings.API_V1_STR)
app.include_router(executions_router, prefix=settings.API_V1_STR)
app.include_router(tools_router, prefix=settings.API_V1_STR)
app.include_router(mcp_router, prefix=settings.API_V1_STR)
app.include_router(stats_router, prefix=settings.API_V1_STR)

# Also mount /api/v1/workflows/{id}/execute directly matching PRD table
app.add_api_route(
    f"{settings.API_V1_STR}/workflows/{{workflow_id}}/execute",
    trigger_workflow_execution,
    methods=["POST"],
    tags=["Workflows"],
    status_code=202,
    response_model=ExecutionResponse,
)


def guessed_type(name: str) -> str:
    """Best-effort content type so mobile clients can open the file directly."""
    return mimetypes.guess_type(name)[0] or "application/octet-stream"


@app.get("/health", tags=["Health"], response_model=HealthResponse)
@app.get(f"{settings.API_V1_STR}/health", tags=["Health"], response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        service="omnigensi-backend",
        version=settings.APP_VERSION,
        workspace_root=str(settings.workspace_path),
    )


@app.get(
    f"{settings.API_V1_STR}/config",
    tags=["System"],
    response_model=ClientConfigResponse,
)
async def client_config(request: Request) -> ClientConfigResponse:
    """Bootstrap endpoint for clients (mobile app and web UI).

    A mobile client should call this once at startup instead of hardcoding the
    API version, stream path template or feature flags.
    """
    base_url = settings.PUBLIC_BASE_URL.rstrip("/") or str(request.base_url).rstrip("/")
    return ClientConfigResponse(
        service="omnigensi-backend",
        version=settings.APP_VERSION,
        api_version="v1",
        api_base_path=settings.API_V1_STR,
        base_url=base_url,
        docs_url=f"{base_url}/docs",
        openapi_url=f"{base_url}/openapi.json",
        streaming={
            "path_template": f"{settings.API_V1_STR}/executions/{{execution_id}}/stream",
            "content_type": "text/event-stream",
            "events": STREAM_EVENTS,
            "keepalive": "comment frames (`: ping`) on idle",
        },
        pagination={
            "params": ["limit", "offset"],
            "default_limit": 50,
            "max_limit": 200,
        },
        features={
            "providers": True,
            "agents": True,
            "workflows": True,
            "executions": True,
            "execution_streaming": True,
            "execution_cancel": True,
            "tool_approval": True,
            "mcp_servers": True,
            "file_download": True,
            "file_upload": False,
            "stats": True,
            "provider_test": True,
            "execution_filters": True,
            "stream_resume": True,
            "workflow_validation": True,
            "execution_retry": True,
            "execution_delete": True,
            "agent_test": True,
            "agent_duplicate": True,
            "workflow_duplicate": True,
            "tool_execution": True,
        },
        limits={"executions_page_size": 50, "max_page_size": 200},
    )


@app.get(f"{settings.API_V1_STR}/files/{{filename:path}}", tags=["Files"])
async def download_workspace_file(filename: str):
    """
    Download endpoint for agent-generated artifacts.

    Used by mobile clients (and browsers without File System Access API) to
    fetch files by the ``filepath``/``filename`` reported in
    ``generated_files`` or in a ``device_file_write`` stream event. Both
    workspace-relative ("report.md") and tool-emitted absolute
    ("/app/workspace/report.md") paths are accepted.
    """
    try:
        file_path = sanitize_workspace_path(filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type=guessed_type(file_path.name),
    )
