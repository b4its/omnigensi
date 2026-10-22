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
    # Prime the token version for this test before any client is built.
    await current_version_via_login()
    yield
    from app.core.database import engine

    # Revocation changes the server's expected version, so the cached value
    # must be dropped for the next test to mint an acceptable token.
    reset_token_version_cache()
    await engine.dispose()


# The server compares every token against the stored version, so test tokens
# must be minted for the current generation. A module-level cache fetches it
# once through the real login endpoint (no extra DB drivers or event loops).
_token_version_cache: dict[str, int] = {}


async def current_version_via_login() -> int:
    """Reads the live token version by performing a real login."""
    if "version" in _token_version_cache:
        return _token_version_cache["version"]

    from app.core.auth import token_version_of
    from app.core.config import settings
    from app.core.rate_limit import login_throttle

    login_throttle.reset()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/v1/auth/login", json={"password": settings.APP_PASSWORD}
        )
        version = token_version_of(resp.json().get("token")) or 0
    _token_version_cache["version"] = version
    return version


def auth_token() -> str:
    """Mints a valid session token matching the server's current generation.

    Synchronous by design: tests build clients outside async context. The
    version is read once via a real login and cached; revocation tests bump it
    and refresh the cache through ``reset_token_version_cache``.
    """
    from app.core.auth import issue_token
    from app.core.auth_store import INITIAL_VERSION

    version = _token_version_cache.get("version", INITIAL_VERSION)
    token, _ = issue_token(token_version=version)
    return token


def reset_token_version_cache() -> None:
    """Called after a test revokes sessions so later tests get a fresh token."""
    _token_version_cache.pop("version", None)


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
