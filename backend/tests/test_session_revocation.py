"""Tests for instant session revocation.

Logout used to only clear the cookie: a bearer token a client still held kept
working for the rest of its 7-day lifetime. Tokens now carry a version that is
compared against a stored value, so bumping it revokes everything at once.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import issue_token, token_version_of, verify_token
from app.core.auth_store import current_token_version
from app.core.config import settings
from app.main import app
from tests.conftest import make_client


def _anon_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture(autouse=True)
async def reset_credentials():
    """Start each test from a clean credential row."""
    from sqlalchemy import delete

    from app.core.database import AsyncSessionLocal
    from app.models.auth_credential import AuthCredential

    async def _clear():
        async with AsyncSessionLocal() as db:
            await db.execute(delete(AuthCredential))
            await db.commit()

    await _clear()
    yield
    await _clear()


async def _login(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/v1/auth/login", json={"password": settings.APP_PASSWORD}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


# --------------------------------------------------------------------------
# Token claim
# --------------------------------------------------------------------------

def test_token_carries_a_version_claim():
    token, _ = issue_token(token_version=7)
    assert token_version_of(token) == 7
    assert verify_token(token) is True


def test_token_version_of_rejects_tampering():
    token, _ = issue_token(token_version=3)
    payload, _, signature = token.partition(".")
    assert token_version_of(f"{payload}x.{signature}") is None
    assert token_version_of("garbage") is None
    assert token_version_of(None) is None


# --------------------------------------------------------------------------
# Logout revokes everywhere
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_issues_a_token_with_the_current_version():
    async with _anon_client() as client:
        token = await _login(client)

        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            expected = await current_token_version(db)
        assert token_version_of(token) == expected

        assert (
            await client.get("/api/v1/agents", headers={"Authorization": f"Bearer {token}"})
        ).status_code == 200


@pytest.mark.asyncio
async def test_logout_immediately_invalidates_the_bearer_token():
    """Previously this token stayed valid for its full TTL."""
    async with _anon_client() as client:
        token = await _login(client)
        headers = {"Authorization": f"Bearer {token}"}

        assert (await client.get("/api/v1/agents", headers=headers)).status_code == 200
        assert (await client.post("/api/v1/auth/logout", headers=headers)).status_code == 200

        after = await client.get("/api/v1/agents", headers=headers)
        assert after.status_code == 401
        assert after.json()["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_logout_revokes_other_clients_too():
    async with _anon_client() as client:
        first = await _login(client)
        second = await _login(client)

        assert (
            await client.get("/api/v1/agents", headers={"Authorization": f"Bearer {second}"})
        ).status_code == 200

        await client.post(
            "/api/v1/auth/logout", headers={"Authorization": f"Bearer {first}"}
        )

        # Every token from the previous generation is dead.
        for token in (first, second):
            assert (
                await client.get(
                    "/api/v1/agents", headers={"Authorization": f"Bearer {token}"}
                )
            ).status_code == 401


@pytest.mark.asyncio
async def test_revoke_sessions_requires_a_session():
    async with _anon_client() as client:
        assert (await client.post("/api/v1/auth/revoke-sessions")).status_code == 401


@pytest.mark.asyncio
async def test_revoke_sessions_kills_all_tokens_without_changing_password():
    async with _anon_client() as client:
        first = await _login(client)
        second = await _login(client)

        revoked = await client.post(
            "/api/v1/auth/revoke-sessions",
            headers={"Authorization": f"Bearer {first}"},
        )
        assert revoked.status_code == 200
        assert revoked.json()["authenticated"] is False

        for token in (first, second):
            assert (
                await client.get(
                    "/api/v1/agents", headers={"Authorization": f"Bearer {token}"}
                )
            ).status_code == 401

        # The password still works, so a new session can be created.
        fresh = await _login(client)
        assert (
            await client.get("/api/v1/agents", headers={"Authorization": f"Bearer {fresh}"})
        ).status_code == 200


@pytest.mark.asyncio
async def test_password_rotation_also_revokes_tokens():
    async with _anon_client() as client:
        token = await _login(client)
        headers = {"Authorization": f"Bearer {token}"}

        changed = await client.post(
            "/api/v1/auth/change-password",
            headers=headers,
            json={
                "current_password": settings.APP_PASSWORD,
                "new_password": "rotatedAfterThis1",
            },
        )
        assert changed.status_code == 200

        assert (
            await client.get("/api/v1/agents", headers=headers)
        ).status_code == 401

        relogin = await client.post(
            "/api/v1/auth/login", json={"password": "rotatedAfterThis1"}
        )
        assert relogin.status_code == 200
        new_token = relogin.json()["token"]
        assert (
            await client.get(
                "/api/v1/agents", headers={"Authorization": f"Bearer {new_token}"}
            )
        ).status_code == 200


@pytest.mark.asyncio
async def test_forged_version_is_rejected():
    """A token claiming a different generation must not be accepted."""
    async with _anon_client() as client:
        await _login(client)
        # Signed with the real secret but a version the server never issued.
        forged, _ = issue_token(token_version=999)
        assert (
            await client.get("/api/v1/agents", headers={"Authorization": f"Bearer {forged}"})
        ).status_code == 401


@pytest.mark.asyncio
async def test_stream_ticket_does_not_bypass_revocation():
    async with make_client() as client:
        token = await _login(client)
        ticket_resp = await client.post(
            "/api/v1/auth/stream-ticket",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert ticket_resp.status_code == 200
        ticket = ticket_resp.json()["ticket"]

    async with _anon_client() as client:
        assert (await client.get(f"/api/v1/agents?token={ticket}")).status_code == 200

        # Revoke, then the previously issued ticket must also fail.
        async with make_client() as authed:
            await authed.post("/api/v1/auth/logout")

        assert (await client.get(f"/api/v1/agents?token={ticket}")).status_code == 401
