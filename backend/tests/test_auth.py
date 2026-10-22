"""Tests for the single-password authentication layer."""

import time

import pytest
from httpx import ASGITransport, AsyncClient

from app.core import auth as auth_module
from app.core.auth import (
    issue_token,
    password_matches,
    verify_token,
)
from app.core.config import settings
from app.main import app
from tests.conftest import auth_headers, make_client


def _anon_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# --------------------------------------------------------------------------
# Token primitives
# --------------------------------------------------------------------------

def test_password_default_is_the_documented_value():
    """Tests run against the shipped default unless the env overrides it."""
    assert settings.APP_PASSWORD


def test_password_matches_is_exact():
    assert password_matches(settings.APP_PASSWORD) is True
    assert password_matches("definitely-wrong") is False
    assert password_matches("") is False
    assert password_matches(None) is False


def test_issue_and_verify_roundtrip():
    token, expires_at = issue_token()
    assert verify_token(token) is True
    assert expires_at > int(time.time())


@pytest.mark.parametrize("bad", ["", None, "garbage", "a.b", "no-dot", "Zm9v.YmFy"])
def test_verify_rejects_malformed_tokens(bad):
    assert verify_token(bad) is False


def test_verify_rejects_tampered_payload():
    token, _ = issue_token()
    payload, _, signature = token.partition(".")
    forged = payload[:-2] + ("AA" if payload[-2:] != "AA" else "BB") + "." + signature
    assert verify_token(forged) is False


def test_verify_rejects_tampered_signature():
    token, _ = issue_token()
    payload, _, signature = token.partition(".")
    assert verify_token(f"{payload}.{signature[:-3]}zzz") is False


def test_verify_rejects_expired_token():
    token, _ = issue_token(ttl_seconds=-10)
    assert verify_token(token) is False


def test_token_is_signed_with_the_configured_secret(monkeypatch):
    token, _ = issue_token()
    monkeypatch.setattr(settings, "AUTH_TOKEN_SECRET", "a-completely-different-secret")
    assert verify_token(token) is False


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_protected_endpoint_requires_a_session():
    async with _anon_client() as client:
        for path in ("/api/v1/agents", "/api/v1/providers", "/api/v1/workflows",
                     "/api/v1/executions", "/api/v1/stats", "/api/v1/mcp/servers"):
            resp = await client.get(path)
            assert resp.status_code == 401, path
            body = resp.json()
            assert body["code"] == "unauthorized"
            assert isinstance(body["detail"], str)
            assert resp.headers.get("www-authenticate") == "Bearer"


@pytest.mark.asyncio
async def test_public_endpoints_stay_open():
    async with _anon_client() as client:
        for path in ("/health", "/api/v1/health", "/api/v1/config", "/openapi.json"):
            resp = await client.get(path)
            assert resp.status_code == 200, path


@pytest.mark.asyncio
async def test_login_with_correct_password_returns_token_and_cookie():
    async with _anon_client() as client:
        resp = await client.post("/api/v1/auth/login", json={"password": settings.APP_PASSWORD})
        assert resp.status_code == 200
        body = resp.json()
        assert body["authenticated"] is True
        assert body["auth_enabled"] is True
        assert body["token"]
        assert verify_token(body["token"])

        cookie = resp.cookies.get(settings.AUTH_COOKIE_NAME)
        assert cookie == body["token"]
        # httpOnly is essential: JS must not be able to read the session.
        set_cookie = resp.headers["set-cookie"]
        assert "httponly" in set_cookie.lower()
        assert "samesite=lax" in set_cookie.lower()


@pytest.mark.asyncio
async def test_login_with_wrong_password_is_rejected():
    async with _anon_client() as client:
        resp = await client.post("/api/v1/auth/login", json={"password": "nope"})
        assert resp.status_code == 401
        assert resp.json()["code"] == "unauthorized"
        assert settings.AUTH_COOKIE_NAME not in resp.cookies


@pytest.mark.asyncio
async def test_login_requires_a_password_field():
    async with _anon_client() as client:
        resp = await client.post("/api/v1/auth/login", json={})
        assert resp.status_code == 422
        assert resp.json()["code"] == "validation_error"


@pytest.mark.asyncio
async def test_cookie_session_grants_access():
    async with _anon_client() as client:
        await client.post("/api/v1/auth/login", json={"password": settings.APP_PASSWORD})
        resp = await client.get("/api/v1/agents")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_bearer_token_grants_access():
    async with _anon_client() as client:
        login = await client.post("/api/v1/auth/login", json={"password": settings.APP_PASSWORD})
        token = login.json()["token"]

        resp = await client.get(
            "/api/v1/agents", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_stream_ticket_grants_access_but_session_token_does_not():
    """EventSource cannot send headers, so URL access uses a short ticket.

    The long-lived session token must never be accepted from a query string:
    it would leak into access logs and Referer headers.
    """
    async with make_client() as client:
        workflows = (await client.get("/api/v1/workflows")).json()
        created = await client.post(
            f"/api/v1/workflows/{workflows[0]['id']}/execute",
            json={"task_prompt": "auth stream test"},
        )
        exec_id = created.json()["id"]
        await client.post(f"/api/v1/executions/{exec_id}/cancel")

    from app.core.auth import issue_stream_ticket

    session_token, _ = issue_token()
    ticket, _ = issue_stream_ticket()

    async with _anon_client() as client:
        anonymous = await client.get(f"/api/v1/executions/{exec_id}/stream")
        assert anonymous.status_code == 401

        # A long-lived session token in the URL is rejected.
        rejected = await client.get(
            f"/api/v1/executions/{exec_id}/stream?token={session_token}"
        )
        assert rejected.status_code == 401

        # A short-lived stream ticket is accepted.
        authed = await client.get(
            f"/api/v1/executions/{exec_id}/stream?token={ticket}"
        )
        assert authed.status_code == 200


@pytest.mark.asyncio
async def test_session_endpoint_reports_state():
    async with _anon_client() as client:
        anon = await client.get("/api/v1/auth/session")
        assert anon.status_code == 200
        assert anon.json()["authenticated"] is False
        assert anon.json()["auth_enabled"] is True

        await client.post("/api/v1/auth/login", json={"password": settings.APP_PASSWORD})
        authed = await client.get("/api/v1/auth/session")
        assert authed.json()["authenticated"] is True


@pytest.mark.asyncio
async def test_logout_clears_the_cookie():
    async with _anon_client() as client:
        await client.post("/api/v1/auth/login", json={"password": settings.APP_PASSWORD})
        assert (await client.get("/api/v1/agents")).status_code == 200

        out = await client.post("/api/v1/auth/logout")
        assert out.status_code == 200
        assert out.json()["authenticated"] is False
        assert (await client.get("/api/v1/agents")).status_code == 401


@pytest.mark.asyncio
async def test_cors_preflight_is_not_blocked_by_auth():
    """Older browsers reject a preflight answered with 401."""
    async with _anon_client() as client:
        resp = await client.options(
            "/api/v1/agents",
            headers={
                "Origin": "http://localhost:5296",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_auth_can_be_disabled(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", False)
    async with _anon_client() as client:
        resp = await client.get("/api/v1/agents")
        assert resp.status_code == 200

        session = await client.get("/api/v1/auth/session")
        assert session.json()["auth_enabled"] is False
        assert session.json()["authenticated"] is True


@pytest.mark.asyncio
async def test_disabled_auth_login_is_a_noop(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", False)
    async with _anon_client() as client:
        resp = await client.post("/api/v1/auth/login", json={"password": "irrelevant"})
        assert resp.status_code == 200
        assert resp.json()["authenticated"] is True
        assert resp.json()["token"] is None


def test_is_public_path_matching():
    for path in ("/health", "/api/v1/health", "/api/v1/config",
                 "/api/v1/auth/login", "/api/v1/auth/session", "/docs"):
        assert auth_module.is_public_path(path) is True, path
    for path in ("/api/v1/agents", "/api/v1/providers", "/api/v1/files/x.md"):
        assert auth_module.is_public_path(path) is False, path


def test_token_from_request_precedence():
    """Bearer wins over query, query wins over cookie."""
    from starlette.datastructures import Headers, QueryParams

    class Cookies(dict):
        pass

    token = "bearer-token"
    headers = Headers({"authorization": f"Bearer {token}"})
    assert (
        auth_module.token_from_request(headers, Cookies({settings.AUTH_COOKIE_NAME: "c"}), QueryParams("token=q"))
        == token
    )

    assert (
        auth_module.token_from_request(
            Headers({}), Cookies({settings.AUTH_COOKIE_NAME: "c"}), QueryParams("token=q")
        )
        == "q"
    )
    assert (
        auth_module.token_from_request(
            Headers({}), Cookies({settings.AUTH_COOKIE_NAME: "c"}), QueryParams("")
        )
        == "c"
    )


@pytest.mark.asyncio
async def test_unauthenticated_response_still_carries_cors_headers():
    """A 401 must be readable by the browser, or it looks like a CORS failure.

    Starlette builds the middleware stack in reverse (last added is
    outermost), so the auth gate must sit inside CORSMiddleware.
    """
    async with _anon_client() as client:
        resp = await client.get(
            "/api/v1/agents", headers={"Origin": "http://localhost:5296"}
        )
        assert resp.status_code == 401
        assert (
            resp.headers.get("access-control-allow-origin") == "http://localhost:5296"
        )
        assert resp.json()["code"] == "unauthorized"


def test_auth_middleware_is_inside_cors():
    """Guards the ordering fix against a future refactor."""
    from app.main import app

    names = [m.cls.__name__ for m in app.user_middleware]
    assert "CORSMiddleware" in names
    assert names.index("CORSMiddleware") < names.index("BaseHTTPMiddleware")


@pytest.mark.asyncio
async def test_public_paths_also_carry_cors_headers():
    async with _anon_client() as client:
        for path in ("/api/v1/health", "/api/v1/config", "/api/v1/auth/session"):
            resp = await client.get(path, headers={"Origin": "http://localhost:5296"})
            assert resp.status_code == 200, path
            assert resp.headers.get("access-control-allow-origin"), path


@pytest.mark.asyncio
async def test_client_config_advertises_auth_requirements():
    """A mobile client must discover how to authenticate before calling."""
    async with _anon_client() as client:
        resp = await client.get("/api/v1/config")
        assert resp.status_code == 200
        auth_info = resp.json()["auth"]
        assert auth_info["enabled"] is True
        assert auth_info["scheme"] == "single-password"
        assert auth_info["login_path"] == "/api/v1/auth/login"
        assert set(auth_info["transports"]) == {"cookie", "bearer", "query"}
        assert auth_info["token_ttl_seconds"] > 0
