"""Persistence bridge between the in-memory MCP manager and the database.

The bridge itself stays synchronous and in-memory (it holds live tool caches),
while this module mirrors registrations into ``mcp_servers`` so operator
changes survive a restart.
"""

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.mcp_bridge import MCPServerConfig, mcp_manager
from app.models.mcp_server import MCPServer

logger = logging.getLogger("omnigensi.mcp")

BUILTIN_SERVERS = {"filesystem-mcp", "memory-mcp"}


def _to_config(row: MCPServer) -> MCPServerConfig:
    return MCPServerConfig(
        name=row.name,
        server_type=row.server_type,
        command=row.command,
        args=list(row.args or []),
        env=dict(row.env or {}),
        url=row.url,
        enabled=row.enabled,
        description=row.description,
    )


async def load_persisted_servers(db: AsyncSession) -> int:
    """Restores registrations from the database into the manager.

    Called on startup. Built-in bridges are registered by the manager itself,
    so only their *state* is restored (an operator may have disabled or
    deleted one).
    """
    rows = (await db.execute(select(MCPServer))).scalars().all()
    restored = 0

    for row in rows:
        if row.deleted:
            # Honour a previous delete, including for built-in bridges.
            if mcp_manager.has_server(row.name):
                mcp_manager.unregister_server(row.name)
            continue

        mcp_manager.register_server(_to_config(row))
        restored += 1

    if restored:
        logger.info("Restored %s MCP server registration(s) from the database", restored)
    return restored


async def upsert_server(db: AsyncSession, config: MCPServerConfig) -> None:
    """Creates or updates the persisted row for a registration."""
    row = (
        await db.execute(select(MCPServer).where(MCPServer.name == config.name))
    ).scalar_one_or_none()

    if row is None:
        row = MCPServer(name=config.name, is_builtin=config.name in BUILTIN_SERVERS)

    row.server_type = config.server_type
    row.command = config.command
    row.args = list(config.args or [])
    row.env = dict(config.env or {})
    row.url = config.url
    row.enabled = config.enabled
    row.description = config.description
    row.deleted = False

    db.add(row)
    await db.commit()


async def delete_server(db: AsyncSession, name: str) -> None:
    """Soft-deletes so a built-in bridge is not resurrected on next boot."""
    row = (
        await db.execute(select(MCPServer).where(MCPServer.name == name))
    ).scalar_one_or_none()

    if row is None:
        # First delete of a built-in: record it so the manager's default
        # registration does not come back on restart.
        if name in BUILTIN_SERVERS:
            db.add(MCPServer(name=name, server_type="stdio", is_builtin=True, deleted=True))
            await db.commit()
        return

    row.deleted = True
    await db.commit()


async def get_persisted(db: AsyncSession, name: str) -> Optional[MCPServer]:
    return (
        await db.execute(select(MCPServer).where(MCPServer.name == name))
    ).scalar_one_or_none()
