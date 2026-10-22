"""Tests for external project integrations, connectivity monitoring, and external API."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app
from app.models.integration_client import IntegrationClient
from tests.conftest import auth_headers, make_client


@pytest.mark.asyncio
async def test_list_clients_auto_seeds_agen_xishie():
    """Listing clients when table is empty auto-seeds agen xishie."""
    async with make_client(authenticated=True) as client:
        resp = await client.get("/api/v1/integrations/clients")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        xishie = next((c for c in data if c["name"] == "agen xishie"), None)
        assert xishie is not None
        assert xishie["target_url"] == "http://localhost:8208/"
        assert xishie["api_key"].startswith("omni_live_")


@pytest.mark.asyncio
async def test_register_and_manage_integration_client():
    """Operator can register, update, regenerate key, and delete a client."""
    async with make_client(authenticated=True) as client:
        # 1. Register a new client (probe_immediately=False to avoid network wait)
        payload = {
            "name": "Test Laravel Microservice",
            "description": "Integration test client",
            "target_url": "http://localhost:9999/",
            "health_endpoint": "/api/health",
            "is_active": True,
            "allowed_models": ["*"],
        }
        res = await client.post(
            "/api/v1/integrations/clients?probe_immediately=false", json=payload
        )
        assert res.status_code == 201
        created = res.json()
        assert created["name"] == "Test Laravel Microservice"
        assert created["api_key"].startswith("omni_live_")
        client_id = created["id"]
        original_key = created["api_key"]

        # 2. Duplicate name is rejected with 409
        dup = await client.post(
            "/api/v1/integrations/clients?probe_immediately=false", json=payload
        )
        assert dup.status_code == 409

        # 3. Update client
        update_res = await client.put(
            f"/api/v1/integrations/clients/{client_id}",
            json={"description": "Updated description", "health_endpoint": "/healthz"},
        )
        assert update_res.status_code == 200
        assert update_res.json()["description"] == "Updated description"
        assert update_res.json()["health_endpoint"] == "/healthz"

        # 4. Regenerate key
        regen_res = await client.post(
            f"/api/v1/integrations/clients/{client_id}/regenerate-key"
        )
        assert regen_res.status_code == 200
        new_key = regen_res.json()["api_key"]
        assert new_key.startswith("omni_live_")
        assert new_key != original_key

        # 5. Delete client
        del_res = await client.delete(f"/api/v1/integrations/clients/{client_id}")
        assert del_res.status_code == 204

        # 6. Verify 404
        get_res = await client.get(f"/api/v1/integrations/clients/{client_id}")
        assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_ping_probe_client():
    """Pinging target returns structured probe result and records latency."""
    async with make_client(authenticated=True) as client:
        # Create a test client pointing to a dummy port
        payload = {
            "name": "Dummy Probe Target",
            "target_url": "http://127.0.0.1:59999/",
            "health_endpoint": "/status",
        }
        res = await client.post(
            "/api/v1/integrations/clients?probe_immediately=false", json=payload
        )
        assert res.status_code == 201
        client_id = res.json()["id"]

        try:
            # Ping it
            ping_res = await client.post(
                f"/api/v1/integrations/clients/{client_id}/ping"
            )
            assert ping_res.status_code == 200
            probe = ping_res.json()
            assert probe["client_id"] == client_id
            assert probe["status"] in ("offline", "online", "degraded")
            assert probe["latency_ms"] is not None

            # Get client to verify DB was updated
            updated_client = (
                await client.get(f"/api/v1/integrations/clients/{client_id}")
            ).json()
            assert updated_client["last_checked_at"] is not None
            assert updated_client["status"] == probe["status"]
        finally:
            await client.delete(f"/api/v1/integrations/clients/{client_id}")


@pytest.mark.asyncio
async def test_external_handshake_with_api_key():
    """External project authenticates with X-API-Key and discovers models."""
    async with make_client(authenticated=True) as op_client:
        # Register a client
        res = await op_client.post(
            "/api/v1/integrations/clients?probe_immediately=false",
            json={
                "name": "Laravel Handshake Client",
                "target_url": "http://localhost:8208/",
            },
        )
        assert res.status_code == 201
        client_data = res.json()
        api_key = client_data["api_key"]
        client_id = client_data["id"]

    try:
        # Unauthenticated request without operator session, using only X-API-Key
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ext_client:
            # 1. No key -> 401
            no_key = await ext_client.get("/api/v1/integrations/v1/handshake")
            assert no_key.status_code == 401

            # 2. Invalid key -> 401
            bad_key = await ext_client.get(
                "/api/v1/integrations/v1/handshake",
                headers={"X-API-Key": "omni_live_invalid_key_123"},
            )
            assert bad_key.status_code == 401

            # 3. Valid key via X-API-Key header -> 200
            good_res = await ext_client.get(
                "/api/v1/integrations/v1/handshake",
                headers={"X-API-Key": api_key},
            )
            assert good_res.status_code == 200
            handshake = good_res.json()
            assert handshake["status"] == "connected"
            assert handshake["client_name"] == "Laravel Handshake Client"
            assert "available_models" in handshake

            # 4. Valid key via Authorization: Bearer -> 200
            bearer_res = await ext_client.get(
                "/api/v1/integrations/v1/handshake",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            assert bearer_res.status_code == 200

            # 5. List models for this client
            models_res = await ext_client.get(
                "/api/v1/integrations/v1/models",
                headers={"X-API-Key": api_key},
            )
            assert models_res.status_code == 200
            assert "data" in models_res.json()

        # Verify inbound telemetry updated in DB
        async with make_client(authenticated=True) as op_client:
            updated = (
                await op_client.get(f"/api/v1/integrations/clients/{client_id}")
            ).json()
            assert updated["inbound_requests_count"] >= 3
            assert updated["last_handshake_at"] is not None

    finally:
        async with make_client(authenticated=True) as op_client:
            await op_client.delete(f"/api/v1/integrations/clients/{client_id}")


@pytest.mark.asyncio
async def test_external_chat_completion_with_api_key(monkeypatch):
    """External project can hit /v1/chat/completions with its API key."""
    async with make_client(authenticated=True) as op_client:
        res = await op_client.post(
            "/api/v1/integrations/clients?probe_immediately=false",
            json={
                "name": "External Chat Client",
                "target_url": "http://localhost:8208/",
            },
        )
        assert res.status_code == 201
        api_key = res.json()["api_key"]
        client_id = res.json()["id"]

    try:
        # Mock create_llm_client to return a predictable response
        class MockLLM:
            async def ainvoke(self, messages):
                class Msg:
                    content = "Halo dari Omnigensi AI!"

                return Msg()

        import app.api.v1.integrations as integrations_module

        monkeypatch.setattr(
            integrations_module, "create_llm_client", lambda *args, **kwargs: MockLLM()
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ext_client:
            chat_res = await ext_client.post(
                "/api/v1/integrations/v1/chat/completions",
                headers={"X-API-Key": api_key},
                json={
                    "messages": [{"role": "user", "content": "Halo Agen"}],
                    "stream": False,
                },
            )
            assert chat_res.status_code == 200
            data = chat_res.json()
            assert data["object"] == "chat.completion"
            assert (
                data["choices"][0]["message"]["content"] == "Halo dari Omnigensi AI!"
            )
            assert data["client"] == "External Chat Client"
            assert data["latency_ms"] >= 0

    finally:
        async with make_client(authenticated=True) as op_client:
            await op_client.delete(f"/api/v1/integrations/clients/{client_id}")
