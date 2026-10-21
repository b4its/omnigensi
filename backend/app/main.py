import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.database import init_db
from app.core.security import sanitize_workspace_path
from app.api.v1.providers import router as providers_router
from app.api.v1.agents import router as agents_router
from app.api.v1.workflows import router as workflows_router
from app.schemas.execution import ExecutionResponse
from app.api.v1.executions import router as executions_router, trigger_workflow_execution
from app.api.v1.tools import router as tools_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("omnigensi")


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
    version="2.0.0",
    description="Dynamic Multi-Agent AIaaS Platform with Local Device & Hardware Bridge",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Development permissive, easily constrained via CORS_ORIGINS
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API v1 Routers
app.include_router(providers_router, prefix=settings.API_V1_STR)
app.include_router(agents_router, prefix=settings.API_V1_STR)
app.include_router(workflows_router, prefix=settings.API_V1_STR)
app.include_router(executions_router, prefix=settings.API_V1_STR)
app.include_router(tools_router, prefix=settings.API_V1_STR)

# Also mount /api/v1/workflows/{id}/execute directly matching PRD table
app.add_api_route(
    f"{settings.API_V1_STR}/workflows/{{workflow_id}}/execute",
    trigger_workflow_execution,
    methods=["POST"],
    tags=["Workflows"],
    status_code=202,
    response_model=ExecutionResponse,
)


@app.get("/health", tags=["Health"])
@app.get(f"{settings.API_V1_STR}/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": "omnigensi-backend",
        "version": "2.0.0",
        "workspace_root": str(settings.workspace_path),
    }


@app.get(f"{settings.API_V1_STR}/files/{{filename:path}}", tags=["Files"])
async def download_workspace_file(filename: str):
    """
    HTTP fallback download endpoint for generated documents.
    """
    try:
        file_path = sanitize_workspace_path(filename)
        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(status_code=404, detail="File not found")
        return FileResponse(
            path=str(file_path),
            filename=file_path.name,
            media_type="application/octet-stream",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
