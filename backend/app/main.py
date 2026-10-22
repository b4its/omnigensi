import logging
import uuid
import mimetypes
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text
import redis.asyncio as aioredis
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.auth import is_public_path, token_from_request, verify_token
from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine, init_db
from app.core.mcp_store import load_persisted_servers
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
from app.api.v1.auth import router as auth_router
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
    # Restore operator-configured MCP servers into the in-memory manager.
    async with AsyncSessionLocal() as db:
        try:
            await load_persisted_servers(db)
        except Exception as exc:  # noqa: BLE001 - startup must not fail
            logger.warning("Could not restore MCP registrations: %s", exc)

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


# Authentication gate.
#
# One shared password protects the whole instance. Health, the client config,
# the docs and the auth endpoints themselves stay public so a client can
# discover the API and sign in.
async def require_session(request: Request, call_next):
    if not settings.AUTH_ENABLED or is_public_path(request.url.path):
        return await call_next(request)

    # CORS preflight never carries credentials; let the CORS layer answer it.
    if request.method == "OPTIONS":
        return await call_next(request)

    token = token_from_request(
        request.headers, request.cookies, request.query_params, allow_query=False
    )
    authenticated = verify_token(token)

    # URL-based access (EventSource, <a download>) may only use a short-lived
    # stream ticket, never the long-lived session token.
    if not authenticated and request.query_params.get("token"):
        authenticated = verify_token(
            request.query_params.get("token"), required_scope="stream"
        )

    if not authenticated:
        # This middleware sits outside the request-id middleware, so the id is
        # minted here too: a 401 must be correlatable like every other error.
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        logger.warning(
            "Rejected unauthenticated %s %s from %s (request_id=%s)",
            request.method,
            request.url.path,
            getattr(getattr(request, "client", None), "host", "unknown"),
            request_id,
        )
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "success": False,
                "detail": "Authentication required",
                "code": "unauthorized",
                "request_id": request_id,
            },
            headers={
                "WWW-Authenticate": "Bearer",
                "X-Request-ID": request_id,
            },
        )
    return await call_next(request)


# Added BEFORE CORS because Starlette makes the last added middleware
# outermost: CORS must wrap this one, otherwise a 401 would reach the browser
# without Access-Control-Allow-Origin and surface as an opaque CORS failure
# instead of the 401 the client needs to act on.
app.add_middleware(BaseHTTPMiddleware, dispatch=require_session)

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
app.include_router(auth_router, prefix=settings.API_V1_STR)
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
async def health_check(response: Response) -> HealthResponse:
    """Liveness *and* readiness: verifies the database and Redis.

    Previously this always answered "healthy", so a monitor stayed green
    during a full outage of Postgres or Redis.
    """
    dependencies: dict[str, str] = {}

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        dependencies["database"] = "ok"
    except Exception as exc:  # noqa: BLE001 - reported to the caller
        dependencies["database"] = f"error: {type(exc).__name__}"

    try:
        redis_conn = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        try:
            await redis_conn.ping()
            dependencies["redis"] = "ok"
        finally:
            await redis_conn.aclose()
    except Exception as exc:  # noqa: BLE001
        dependencies["redis"] = f"error: {type(exc).__name__}"

    healthy = all(value == "ok" for value in dependencies.values())
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        logger.warning("Health check degraded: %s", dependencies)

    return HealthResponse(
        status="healthy" if healthy else "degraded",
        service="omnigensi-backend",
        version=settings.APP_VERSION,
        workspace_root=str(settings.workspace_path),
        dependencies=dependencies,
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
        auth={
            "enabled": settings.AUTH_ENABLED,
            "scheme": "single-password",
            "login_path": f"{settings.API_V1_STR}/auth/login",
            "session_path": f"{settings.API_V1_STR}/auth/session",
            "transports": ["cookie", "bearer", "query"],
            "token_ttl_seconds": settings.AUTH_TOKEN_TTL_SECONDS,
        },
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
