"""Shared test fixtures.

The API is protected by a single operator password, so every test client
except the auth tests needs a valid session. ``authed_client`` provides one.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app


@pytest_asyncio.fixture(autouse=True)
async def cleanup_db_connections():
    yield
    from app.core.database import engine

    await engine.dispose()


def auth_token() -> str:
    """Mints a valid session token for tests without going through /login."""
    from app.core.auth import issue_token

    token, _ = issue_token()
    return token


def auth_headers() -> dict:
    return {"Authorization": f"Bearer {auth_token()}"}


def make_client(*, authenticated: bool = True) -> AsyncClient:
    """Builds an ASGI client, authenticated by default."""
    headers = auth_headers() if authenticated and settings.AUTH_ENABLED else None
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=headers,
    )


@pytest.fixture
def client_headers() -> dict:
    """Bearer header usable with manually built clients."""
    return auth_headers()


@pytest_asyncio.fixture
async def authed_client():
    async with make_client(authenticated=True) as client:
        yield client
