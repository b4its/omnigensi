"""Tests for password rotation, TLS defaults, MCP persistence and file admin."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core import auth as auth_module
from app.core.auth import (
    hash_password,
    issue_stream_ticket,
    issue_token,
    password_matches,
    verify_password_hash,
    verify_token,
)
from app.core.config import settings
from app.main import app
from tests.conftest import make_client


def _anon_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture(autouse=True)
async def clean_credentials():
    """Each test starts from the environment default."""
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


# --------------------------------------------------------------------------
# Password hashing primitives
# --------------------------------------------------------------------------

def test_hash_is_salted_and_verifies():
    first = hash_password("correct horse")
    second = hash_password("correct horse")

    assert first != second, "each hash must use a fresh salt"
    assert first.startswith("pbkdf2_sha256$")
    assert verify_password_hash("correct horse", first) is True
    assert verify_password_hash("wrong", first) is False


def test_verify_password_hash_rejects_malformed_input():
    for bad in ("", "not-a-hash", "pbkdf2_sha256$abc$def", "md5$1$s$h"):
        assert verify_password_hash("x", bad) is False


def test_password_matches_prefers_stored_hash():
    stored = hash_password("rotated-secret")
    assert password_matches("rotated-secret", stored) is True
    # The env default must no longer work once a hash exists.
    assert password_matches(settings.APP_PASSWORD, stored) is False
    # Without a stored hash the env value is used.
    assert password_matches(settings.APP_PASSWORD, None) is True


# --------------------------------------------------------------------------
# Token scopes
# --------------------------------------------------------------------------

def test_session_and_stream_tokens_are_not_interchangeable():
    session_token, _ = issue_token()
    ticket, _ = issue_stream_ticket()

    assert verify_token(session_token) is True
    assert verify_token(ticket) is False, "a ticket must not act as a session"

    assert verify_token(session_token, required_scope="stream") is False
    assert verify_token(ticket, required_scope="stream") is True


def test_stream_ticket_expires_quickly():
    import time

    ticket, expires_at = issue_stream_ticket(ttl_seconds=30)
    assert expires_at - int(time.time()) <= 31
    assert verify_token(ticket, required_scope="stream") is True


# --------------------------------------------------------------------------
# /auth/stream-ticket
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stream_ticket_requires_a_session():
    async with _anon_client() as client:
        assert (await client.post("/api/v1/auth/stream-ticket")).status_code == 401


@pytest.mark.asyncio
async def test_stream_ticket_issued_for_a_valid_session():
    async with _anon_client() as client:
        login = await client.post(
            "/api/v1/auth/login", json={"password": settings.APP_PASSWORD}
        )
        token = login.json()["token"]

        resp = await client.post(
            "/api/v1/auth/stream-ticket", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert verify_token(body["ticket"], required_scope="stream") is True

        # The ticket works in a query string...
        ok = await client.get(f"/api/v1/agents?token={body['ticket']}")
        assert ok.status_code == 200

    # ...while the session token does not. A fresh client is used so the
    # login cookie cannot mask the result.
    async with _anon_client() as fresh:
        rejected = await fresh.get(f"/api/v1/agents?token={token}")
        assert rejected.status_code == 401


# --------------------------------------------------------------------------
# /auth/change-password
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_change_password_requires_session():
    async with _anon_client() as client:
        resp = await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": settings.APP_PASSWORD, "new_password": "newSecret99"},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_change_password_rejects_wrong_current():
    async with make_client() as client:
        resp = await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "not-it", "new_password": "newSecret99"},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_change_password_rejects_short_and_default():
    async with make_client() as client:
        short = await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": settings.APP_PASSWORD, "new_password": "abc"},
        )
        assert short.status_code == 422

        default = await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": settings.APP_PASSWORD, "new_password": "123"},
        )
        assert default.status_code in (400, 422)


@pytest.mark.asyncio
async def test_change_password_rotates_and_clears_cookie():
    async with _anon_client() as client:
        login = await client.post(
            "/api/v1/auth/login", json={"password": settings.APP_PASSWORD}
        )
        token = login.json()["token"]

        changed = await client.post(
            "/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={"current_password": settings.APP_PASSWORD, "new_password": "rotatedSecret1"},
        )
        assert changed.status_code == 200
        assert changed.json()["authenticated"] is False

        # Old password no longer works; the new one does.
        assert (
            await client.post("/api/v1/auth/login", json={"password": settings.APP_PASSWORD})
        ).status_code == 401
        assert (
            await client.post("/api/v1/auth/login", json={"password": "rotatedSecret1"})
        ).status_code == 200


@pytest.mark.asyncio
async def test_change_password_rejects_unchanged_value():
    async with make_client() as client:
        resp = await client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": settings.APP_PASSWORD,
                "new_password": settings.APP_PASSWORD,
            },
        )
        assert resp.status_code in (400, 422)


# --------------------------------------------------------------------------
# TLS default
# --------------------------------------------------------------------------

def test_provider_tls_verification_defaults_to_on():
    """Provider calls carry the API key, so verification must be opt-out."""
    assert settings.PROVIDER_TLS_VERIFY is True


def test_no_module_disables_tls_verification_unconditionally():
    from pathlib import Path

    app_dir = Path(__file__).resolve().parent.parent / "app"
    offenders = [
        str(p)
        for p in app_dir.rglob("*.py")
        if "verify=False" in p.read_text(encoding="utf-8")
    ]
    assert not offenders, f"hardcoded verify=False found in: {offenders}"


# --------------------------------------------------------------------------
# MCP persistence
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mcp_registration_persists_to_the_database():
    name = "persist-contract-mcp"
    async with make_client() as client:
        try:
            created = await client.post(
                "/api/v1/mcp/servers",
                json={
                    "name": name,
                    "server_type": "stdio",
                    "command": "python",
                    "args": ["-c", "print(1)"],
                    "description": "persistence contract",
                },
            )
            assert created.status_code == 201

            from sqlalchemy import select

            from app.core.database import AsyncSessionLocal
            from app.models.mcp_server import MCPServer

            async with AsyncSessionLocal() as db:
                row = (
                    await db.execute(select(MCPServer).where(MCPServer.name == name))
                ).scalar_one_or_none()
            assert row is not None
            assert row.command == "python"
            assert row.deleted is False

            # Toggling persists too.
            await client.patch(f"/api/v1/mcp/servers/{name}", json={"enabled": False})
            async with AsyncSessionLocal() as db:
                row = (
                    await db.execute(select(MCPServer).where(MCPServer.name == name))
                ).scalar_one()
            assert row.enabled is False
        finally:
            await client.delete(f"/api/v1/mcp/servers/{name}")


@pytest.mark.asyncio
async def test_mcp_delete_is_remembered():
    """Deleting a built-in must not be undone by the startup defaults."""
    async with make_client() as client:
        # Create then delete a custom server: the row is soft-deleted.
        await client.post(
            "/api/v1/mcp/servers",
            json={"name": "soft-delete-mcp", "server_type": "stdio", "command": "echo"},
        )
        assert (await client.delete("/api/v1/mcp/servers/soft-delete-mcp")).status_code == 204

        from sqlalchemy import select

        from app.core.database import AsyncSessionLocal
        from app.core.mcp_store import load_persisted_servers
        from app.engine.mcp_bridge import mcp_manager
        from app.models.mcp_server import MCPServer

        async with AsyncSessionLocal() as db:
            row = (
                await db.execute(
                    select(MCPServer).where(MCPServer.name == "soft-delete-mcp")
                )
            ).scalar_one()
            assert row.deleted is True

            # Restoring must not resurrect it.
            await load_persisted_servers(db)
        assert mcp_manager.has_server("soft-delete-mcp") is False


# --------------------------------------------------------------------------
# Workspace file administration
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_file_listing_and_download_roundtrip():
    from app.core.config import settings as s

    target = s.workspace_path / "listing_probe.md"
    target.write_text("# probe", encoding="utf-8")
    try:
        async with make_client() as client:
            listing = await client.get("/api/v1/files?limit=200")
            assert listing.status_code == 200
            body = listing.json()
            assert body["total"] >= 1
            assert "listing_probe.md" in [f["path"] for f in body["files"]]
            assert body["total_bytes"] > 0

            # The original download URL shape still works.
            download = await client.get("/api/v1/files/listing_probe.md")
            assert download.status_code == 200
            assert download.content == b"# probe"

            # Search narrows the list.
            filtered = await client.get("/api/v1/files?q=listing_probe")
            assert filtered.json()["total"] == 1
    finally:
        target.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_file_delete_and_traversal_guard():
    from app.core.config import settings as s

    target = s.workspace_path / "delete_probe.md"
    target.write_text("x", encoding="utf-8")

    async with make_client() as client:
        assert (await client.delete("/api/v1/files/delete_probe.md")).status_code == 204
        assert not target.exists()
        assert (await client.delete("/api/v1/files/delete_probe.md")).status_code == 404

        traversal = await client.delete("/api/v1/files/..%2F..%2Fetc%2Fpasswd")
        assert traversal.status_code == 400


@pytest.mark.asyncio
async def test_file_cleanup_respects_age():
    import os
    import time

    from app.core.config import settings as s

    old = s.workspace_path / "cleanup_old.md"
    fresh = s.workspace_path / "cleanup_fresh.md"
    old.write_text("old", encoding="utf-8")
    fresh.write_text("fresh", encoding="utf-8")

    # Age the first file by three days.
    three_days_ago = time.time() - 3 * 86400
    os.utime(old, (three_days_ago, three_days_ago))

    try:
        async with make_client() as client:
            result = await client.post("/api/v1/files/cleanup?older_than_days=1")
            assert result.status_code == 200
            body = result.json()
            assert body["deleted"] >= 1
            assert body["freed_bytes"] >= 3

        assert not old.exists(), "an old artifact must be removed"
        assert fresh.exists(), "a recent artifact must be kept"
    finally:
        old.unlink(missing_ok=True)
        fresh.unlink(missing_ok=True)


def test_auth_module_still_exposes_the_public_helpers():
    """Guard against the earlier accidental overwrite of issue_token."""
    for name in (
        "issue_token",
        "issue_stream_ticket",
        "verify_token",
        "password_matches",
        "hash_password",
        "token_from_request",
        "is_public_path",
    ):
        assert hasattr(auth_module, name), name
