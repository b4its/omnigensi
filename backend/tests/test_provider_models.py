"""Tests for provider model discovery, selection and response testing.

Network calls are stubbed with httpx.MockTransport so the suite never
depends on a real LLM provider.
"""

import json
import uuid
from typing import Any, Callable, Dict

import httpx
import pytest

from app.engine import provider_probe
from app.main import app
from httpx import ASGITransport, AsyncClient


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# Captured once, before any patching, so the factory never calls itself.
_REAL_ASYNC_CLIENT = httpx.AsyncClient


def _mock_client_factory(handler: Callable[[httpx.Request], httpx.Response]):
    """Patch provider_probe to use a stub transport instead of the network."""

    def _client_factory(*_args, **_kwargs):
        return _REAL_ASYNC_CLIENT(transport=httpx.MockTransport(handler))

    return _client_factory


MODELS_PAYLOAD = {
    "data": [
        {"id": "fake-small", "context_length": 4096, "name": "Fake Small"},
        {"id": "fake-large", "context_length": 128000, "name": "Fake Large"},
    ]
}


def _openai_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/models"):
        return httpx.Response(200, json=MODELS_PAYLOAD)
    if request.url.path.endswith("/chat/completions"):
        body = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"role": "assistant", "content": f"REPLY[{body['model']}]"}}
                ],
                "usage": {"prompt_tokens": 7, "completion_tokens": 3},
            },
        )
    return httpx.Response(404, json={"error": "unexpected path"})


@pytest.fixture
def stub_network(monkeypatch):
    monkeypatch.setattr(
        provider_probe.httpx, "AsyncClient", _mock_client_factory(_openai_handler)
    )
    return _openai_handler


async def _create_provider(client: AsyncClient, name: str, **extra) -> Dict[str, Any]:
    payload = {
        "name": name,
        "provider_type": "custom",
        "base_url": "http://stub.local/v1",
        "api_key": "sk-stub",
        "is_active": True,
    }
    payload.update(extra)
    resp = await client.post("/api/v1/providers", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_discover_models_normalises_openai_payload(monkeypatch, stub_network):
    result = await provider_probe.discover_models("http://stub.local/v1", "sk")
    assert result.ok is True
    assert [m["model_id"] for m in result.models] == ["fake-small", "fake-large"]
    assert result.models[1]["context_length"] == 128000
    assert result.models[0]["display_name"] == "Fake Small"


@pytest.mark.asyncio
async def test_discover_models_reports_auth_failure(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "bad key"})

    monkeypatch.setattr(
        provider_probe.httpx, "AsyncClient", _mock_client_factory(handler)
    )
    result = await provider_probe.discover_models("http://stub.local/v1", "nope")
    assert result.ok is False
    assert result.status_code == 401
    assert "Authentication failed" in (result.error or "")


@pytest.mark.asyncio
async def test_discover_models_reports_unreachable(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    monkeypatch.setattr(
        provider_probe.httpx, "AsyncClient", _mock_client_factory(handler)
    )
    result = await provider_probe.discover_models("http://stub.local/v1", "k")
    assert result.ok is False
    assert result.error


@pytest.mark.asyncio
async def test_probe_chat_returns_reply_and_usage(monkeypatch, stub_network):
    result = await provider_probe.probe_chat(
        "http://stub.local/v1", "sk", "fake-large", "hi"
    )
    assert result.ok is True
    assert result.response_text == "REPLY[fake-large]"
    assert result.prompt_tokens == 7
    assert result.completion_tokens == 3


@pytest.mark.asyncio
async def test_probe_chat_surfaces_error_body(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429, json={"error": {"message": "rate limited, try later"}}
        )

    monkeypatch.setattr(
        provider_probe.httpx, "AsyncClient", _mock_client_factory(handler)
    )
    result = await provider_probe.probe_chat("http://stub.local/v1", "sk", "m", "hi")
    assert result.ok is False
    assert "429" in (result.error or "")
    assert "rate limited" in (result.error or "")


@pytest.mark.asyncio
async def test_sync_stores_models_and_selects_default(stub_network):
    async with _client() as client:
        provider = await _create_provider(client, "sync-provider")
        pid = provider["id"]
        try:
            sync = await client.post(f"/api/v1/providers/{pid}/models/sync")
            assert sync.status_code == 200
            body = sync.json()
            assert body["ok"] is True
            assert body["added"] == 2
            assert body["total_stored"] == 2

            registry = await client.get(f"/api/v1/providers/{pid}/model-registry")
            rows = registry.json()
            assert {r["model_id"] for r in rows} == {"fake-small", "fake-large"}
            # A default is chosen automatically so the picker is never empty.
            assert sum(1 for r in rows if r["is_default"]) == 1

            refreshed = await client.get(f"/api/v1/providers/{pid}")
            assert refreshed.json()["default_model"] in {"fake-small", "fake-large"}
        finally:
            await client.delete(f"/api/v1/providers/{pid}")


@pytest.mark.asyncio
async def test_sync_is_idempotent(stub_network):
    async with _client() as client:
        provider = await _create_provider(client, "idempotent-provider")
        pid = provider["id"]
        try:
            first = (await client.post(f"/api/v1/providers/{pid}/models/sync")).json()
            second = (await client.post(f"/api/v1/providers/{pid}/models/sync")).json()
            assert first["added"] == 2
            assert second["added"] == 0
            assert second["updated"] == 2
            assert second["total_stored"] == 2
        finally:
            await client.delete(f"/api/v1/providers/{pid}")


@pytest.mark.asyncio
async def test_sync_failure_reports_error_without_fake_models(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("unreachable", request=request)

    monkeypatch.setattr(
        provider_probe.httpx, "AsyncClient", _mock_client_factory(handler)
    )
    async with _client() as client:
        provider = await _create_provider(client, "dead-provider")
        pid = provider["id"]
        try:
            sync = await client.post(f"/api/v1/providers/{pid}/models/sync")
            assert sync.status_code == 200
            body = sync.json()
            assert body["ok"] is False
            assert body["added"] == 0
            assert body["total_stored"] == 0
            assert body["error"]

            registry = await client.get(f"/api/v1/providers/{pid}/model-registry")
            assert registry.json() == []
        finally:
            await client.delete(f"/api/v1/providers/{pid}")


@pytest.mark.asyncio
async def test_selecting_default_model_updates_provider(stub_network):
    async with _client() as client:
        provider = await _create_provider(client, "select-provider")
        pid = provider["id"]
        try:
            await client.post(f"/api/v1/providers/{pid}/models/sync")

            chosen = await client.put(
                f"/api/v1/providers/{pid}/default-model", json={"model_id": "fake-small"}
            )
            assert chosen.status_code == 200
            assert chosen.json()["model_id"] == "fake-small"
            assert chosen.json()["is_default"] is True

            registry = (await client.get(f"/api/v1/providers/{pid}/model-registry")).json()
            assert [r["model_id"] for r in registry if r["is_default"]] == ["fake-small"]

            refreshed = await client.get(f"/api/v1/providers/{pid}")
            assert refreshed.json()["default_model"] == "fake-small"
        finally:
            await client.delete(f"/api/v1/providers/{pid}")


@pytest.mark.asyncio
async def test_selecting_unknown_model_is_rejected(stub_network):
    async with _client() as client:
        provider = await _create_provider(client, "unknown-model-provider")
        pid = provider["id"]
        try:
            resp = await client.put(
                f"/api/v1/providers/{pid}/default-model",
                json={"model_id": "not-registered"},
            )
            assert resp.status_code == 404
            assert resp.json()["code"] == "not_found"
        finally:
            await client.delete(f"/api/v1/providers/{pid}")


@pytest.mark.asyncio
async def test_chat_test_returns_real_response(stub_network):
    async with _client() as client:
        provider = await _create_provider(client, "chat-provider")
        pid = provider["id"]
        try:
            await client.post(f"/api/v1/providers/{pid}/models/sync")
            await client.put(
                f"/api/v1/providers/{pid}/default-model", json={"model_id": "fake-large"}
            )

            # Default model is used when none is passed
            resp = await client.post(
                f"/api/v1/providers/{pid}/chat-test", json={"prompt": "ping"}
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["ok"] is True
            assert body["model_id"] == "fake-large"
            assert body["response_text"] == "REPLY[fake-large]"

            # An explicit model overrides the default
            override = await client.post(
                f"/api/v1/providers/{pid}/chat-test",
                json={"model_id": "fake-small", "prompt": "ping"},
            )
            assert override.json()["response_text"] == "REPLY[fake-small]"
        finally:
            await client.delete(f"/api/v1/providers/{pid}")


@pytest.mark.asyncio
async def test_chat_test_requires_a_model(stub_network):
    async with _client() as client:
        provider = await _create_provider(client, "no-model-provider")
        pid = provider["id"]
        try:
            resp = await client.post(
                f"/api/v1/providers/{pid}/chat-test", json={"prompt": "ping"}
            )
            assert resp.status_code == 400
            assert "No model selected" in resp.json()["detail"]
        finally:
            await client.delete(f"/api/v1/providers/{pid}")


@pytest.mark.asyncio
async def test_chat_test_reports_failure(stub_network, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json=MODELS_PAYLOAD)
        return httpx.Response(401, json={"error": "bad key"})

    monkeypatch.setattr(
        provider_probe.httpx, "AsyncClient", _mock_client_factory(handler)
    )
    async with _client() as client:
        provider = await _create_provider(client, "failing-chat-provider")
        pid = provider["id"]
        try:
            await client.post(f"/api/v1/providers/{pid}/models/sync")
            resp = await client.post(
                f"/api/v1/providers/{pid}/chat-test", json={"prompt": "ping"}
            )
            body = resp.json()
            assert body["ok"] is False
            assert "Authentication failed" in (body["error"] or "")
            assert body["response_text"] is None
        finally:
            await client.delete(f"/api/v1/providers/{pid}")


@pytest.mark.asyncio
async def test_create_provider_with_auto_sync(stub_network):
    async with _client() as client:
        resp = await client.post(
            "/api/v1/providers?auto_sync_models=true",
            json={
                "name": "auto-sync-provider",
                "provider_type": "custom",
                "base_url": "http://stub.local/v1",
                "api_key": "sk-stub",
                "is_active": True,
            },
        )
        assert resp.status_code == 201, resp.text
        created = resp.json()
        pid = created["id"]
        try:
            # Registration auto-selected a default in the same request.
            assert created["default_model"] in {"fake-small", "fake-large"}
            registry = (
                await client.get(f"/api/v1/providers/{pid}/model-registry")
            ).json()
            assert len(registry) == 2
        finally:
            await client.delete(f"/api/v1/providers/{pid}")


@pytest.mark.asyncio
async def test_draft_discovery_and_chat_do_not_persist(stub_network):
    async with _client() as client:
        before = (await client.get("/api/v1/providers?limit=100")).json()
        before_ids = {p["id"] for p in before}

        discovered = await client.post(
            "/api/v1/providers/discover-draft",
            json={"base_url": "http://stub.local/v1", "api_key": "sk-stub"},
        )
        assert discovered.status_code == 200
        assert discovered.json()["ok"] is True
        assert [m["id"] for m in discovered.json()["models"]] == [
            "fake-small",
            "fake-large",
        ]

        chatted = await client.post(
            "/api/v1/providers/chat-test-draft",
            json={
                "base_url": "http://stub.local/v1",
                "api_key": "sk-stub",
                "model_id": "fake-small",
                "prompt": "hi",
            },
        )
        assert chatted.status_code == 200
        assert chatted.json()["response_text"] == "REPLY[fake-small]"

        after = (await client.get("/api/v1/providers?limit=100")).json()
        # Nothing may be created by a draft probe.
        assert {p["id"] for p in after} == before_ids


@pytest.mark.asyncio
async def test_models_endpoint_falls_back_to_stored_rows(stub_network, monkeypatch):
    """A transient outage must not invent models, only reuse stored ones."""
    async with _client() as client:
        provider = await _create_provider(client, "fallback-provider")
        pid = provider["id"]
        try:
            await client.post(f"/api/v1/providers/{pid}/models/sync")

            def handler(request: httpx.Request) -> httpx.Response:
                raise httpx.ConnectError("down", request=request)

            monkeypatch.setattr(
                provider_probe.httpx, "AsyncClient", _mock_client_factory(handler)
            )

            resp = await client.get(f"/api/v1/providers/{pid}/models")
            assert resp.status_code == 200
            ids = {m["id"] for m in resp.json()}
            assert ids == {"fake-small", "fake-large"}
        finally:
            await client.delete(f"/api/v1/providers/{pid}")


@pytest.mark.asyncio
async def test_deleting_provider_cascades_models(stub_network):
    async with _client() as client:
        provider = await _create_provider(client, "cascade-provider")
        pid = provider["id"]
        await client.post(f"/api/v1/providers/{pid}/models/sync")
        assert len((await client.get(f"/api/v1/providers/{pid}/model-registry")).json()) == 2

        assert (await client.delete(f"/api/v1/providers/{pid}")).status_code == 204

        # The provider (and therefore its registry) is gone.
        assert (await client.get(f"/api/v1/providers/{pid}")).status_code == 404
