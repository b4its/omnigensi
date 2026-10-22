"""Workspace artifact listing and cleanup.

Agent tools write documents into ``WORKSPACE_ROOT`` without any bound, and the
only HTTP surface was a single-file download. Operators had to shell into the
container to see or prune what the system had produced.
"""

import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.core.auth import verify_token
from app.core.config import settings
from app.core.security import sanitize_workspace_path

router = APIRouter(prefix="/files", tags=["Files"])


class WorkspaceFile(BaseModel):
    """One artifact on disk."""

    filename: str
    path: str = Field(description="Workspace-relative path, usable with GET /files/{path}")
    size_bytes: int
    modified_at: str
    content_type: str


class WorkspaceFileList(BaseModel):
    total: int
    total_bytes: int
    files: List[WorkspaceFile]


class CleanupResult(BaseModel):
    deleted: int
    freed_bytes: int
    remaining: int


def _describe(path: Path, root: Path) -> WorkspaceFile:
    stat = path.stat()
    return WorkspaceFile(
        filename=path.name,
        path=path.relative_to(root).as_posix(),
        size_bytes=stat.st_size,
        modified_at=datetime.fromtimestamp(
            stat.st_mtime, tz=timezone.utc
        ).isoformat(),
        content_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
    )


@router.get("", response_model=WorkspaceFileList)
async def list_workspace_files(
    q: Optional[str] = Query(None, max_length=120, description="Filter by filename"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> Any:
    """Lists generated artifacts, newest first."""
    root = settings.workspace_path
    entries: List[tuple[float, Path]] = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if q and q.lower() not in path.name.lower():
            continue
        try:
            entries.append((path.stat().st_mtime, path))
        except OSError:
            continue

    entries.sort(key=lambda item: item[0], reverse=True)
    total = len(entries)
    total_bytes = sum(p.stat().st_size for _, p in entries if p.exists())
    page = entries[offset : offset + limit]

    return WorkspaceFileList(
        total=total,
        total_bytes=total_bytes,
        files=[_describe(path, root) for _, path in page],
    )


@router.get("/{filename:path}")
async def download_workspace_file(filename: str) -> Any:
    """Streams a single artifact.

    Accepts both workspace-relative ("report.md") and tool-emitted absolute
    ("/app/workspace/report.md") paths.
    """
    try:
        file_path = sanitize_workspace_path(filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type=mimetypes.guess_type(file_path.name)[0] or "application/octet-stream",
    )


@router.delete("/{filename:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace_file(filename: str) -> None:
    """Removes a single artifact.

    Path traversal is rejected by ``sanitize_workspace_path``.
    """
    try:
        path = sanitize_workspace_path(filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    path.unlink()
    return None


@router.post("/cleanup", response_model=CleanupResult)
async def cleanup_workspace(
    older_than_days: int = Query(
        0,
        ge=0,
        le=3650,
        description="Only delete files older than this many days (0 = all)",
    ),
) -> Any:
    """Deletes old artifacts to bound disk usage.

    ``older_than_days=0`` removes everything, which is useful for a reset but
    destructive, so callers should confirm with the user first.
    """
    root = settings.workspace_path
    cutoff = datetime.now(timezone.utc).timestamp() - older_than_days * 86400

    deleted = 0
    freed = 0
    remaining = 0

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            stat = path.stat()
        except OSError:
            continue

        if stat.st_mtime > cutoff:
            remaining += 1
            continue

        try:
            path.unlink()
            deleted += 1
            freed += stat.st_size
        except OSError:
            remaining += 1

    return CleanupResult(deleted=deleted, freed_bytes=freed, remaining=remaining)
