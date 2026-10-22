"""Server-side session state: the current token version.

Tokens stay stateless (signed, no session table), but they embed a version
number compared against this value on every request. Bumping it revokes every
outstanding token immediately - what "log out everywhere" and a password
rotation must actually do.
"""

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth_credential import AuthCredential

logger = logging.getLogger("omnigensi.auth")

# 1-based so that "no row yet" (0) differs from any revoked generation.
INITIAL_VERSION = 1


async def current_token_version(db: AsyncSession) -> int:
    """Version a token must carry to be accepted."""
    row = (
        await db.execute(select(AuthCredential).limit(1))
    ).scalar_one_or_none()
    return row.token_version if row else INITIAL_VERSION


async def bump_token_version(db: AsyncSession) -> int:
    """Invalidates every outstanding session token."""
    row = (
        await db.execute(select(AuthCredential).limit(1))
    ).scalar_one_or_none()

    if row is None:
        # No credential row yet: create one so the bump is persisted and the
        # env password keeps working (password_hash stays empty -> env fallback).
        row = AuthCredential(password_hash="", token_version=INITIAL_VERSION + 1)
        db.add(row)
    else:
        row.token_version = (row.token_version or INITIAL_VERSION) + 1

    await db.commit()
    await db.refresh(row)
    logger.info("Session token version bumped to %s", row.token_version)
    return row.token_version


async def stored_password_hash(db: AsyncSession) -> Optional[str]:
    """The rotated password hash, or None to fall back to the env value."""
    row = (
        await db.execute(select(AuthCredential).limit(1))
    ).scalar_one_or_none()
    if not row or not row.password_hash:
        return None
    return row.password_hash
