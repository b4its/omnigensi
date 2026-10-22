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
    """Authenticated client; the API is password protected."""
    from tests.conftest import make_client

    return make_client(authenticated=True)


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
async def test_default_model_must_answer_a_completion(stub_network, monkeypatch):
    """A listed model whose upstream fails must not become the default."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json=MODELS_PAYLOAD)
        # Chat completions fail: upstream out of credits / bad auth.
        return httpx.Response(
            503, json={"error": {"message": "no credits remaining"}}
        )

    monkeypatch.setattr(
        provider_probe.httpx, "AsyncClient", _mock_client_factory(handler)
    )
    async with _client() as client:
        provider = await _create_provider(client, "broken-default-provider")
        pid = provider["id"]
        try:
            await client.post(f"/api/v1/providers/{pid}/models/sync")
            before = (await client.get(f"/api/v1/providers/{pid}")).json()["default_model"]

            resp = await client.put(
                f"/api/v1/providers/{pid}/default-model", json={"model_id": "fake-large"}
            )
            assert resp.status_code == 422
            detail = resp.json()["detail"]
            assert "did not answer a test completion" in detail
            assert "no credits remaining" in detail

            # The selection was not persisted.
            after = (await client.get(f"/api/v1/providers/{pid}")).json()["default_model"]
            assert after == before
        finally:
            await client.delete(f"/api/v1/providers/{pid}")


@pytest.mark.asyncio
async def test_default_model_verification_can_be_skipped(stub_network, monkeypatch):
    """Operators can force a selection when the upstream is intentionally cold."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json=MODELS_PAYLOAD)
        return httpx.Response(503, json={"error": {"message": "cold"}})

    monkeypatch.setattr(
        provider_probe.httpx, "AsyncClient", _mock_client_factory(handler)
    )
    async with _client() as client:
        provider = await _create_provider(client, "skip-verify-provider")
        pid = provider["id"]
        try:
            await client.post(f"/api/v1/providers/{pid}/models/sync")
            resp = await client.put(
                f"/api/v1/providers/{pid}/default-model",
                json={"model_id": "fake-large", "verify": False},
            )
            assert resp.status_code == 200
            assert resp.json()["is_default"] is True
            refreshed = (await client.get(f"/api/v1/providers/{pid}")).json()
            assert refreshed["default_model"] == "fake-large"
        finally:
            await client.delete(f"/api/v1/providers/{pid}")


@pytest.mark.asyncio
async def test_resync_keeps_a_healthy_default(stub_network):
    """Re-syncing must not clobber a working selection with a fresh pick."""
    async with _client() as client:
        provider = await _create_provider(client, "keep-default-provider")
        pid = provider["id"]
        try:
            await client.post(f"/api/v1/providers/{pid}/models/sync")
            await client.put(
                f"/api/v1/providers/{pid}/default-model", json={"model_id": "fake-large"}
            )
            await client.post(f"/api/v1/providers/{pid}/models/sync")

            refreshed = (await client.get(f"/api/v1/providers/{pid}")).json()
            assert refreshed["default_model"] == "fake-large"
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


def _mutable_models_handler(models: Dict[str, Any]):
    """Handler whose /models list is read from ``models['ids']`` each call."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(
                200,
                json={"data": [{"id": mid, "context_length": 4096} for mid in models["ids"]]},
            )
        if request.url.path.endswith("/chat/completions"):
            body = json.loads(request.content)
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": f"REPLY[{body['model']}]"}}]},
            )
        return httpx.Response(404, json={"error": "unexpected path"})

    return handler


@pytest.mark.asyncio
async def test_sync_default_only_marks_vanished_models():
    """Without prune, a model that disappears is flagged, not deleted."""
    state = {"ids": ["m-a", "m-b"]}
    async with _client() as client:
        provider = await _create_provider(client, "mark-only-provider")
        pid = provider["id"]
        try:
            from app.engine import provider_probe as pp

            pp.httpx.AsyncClient = _mock_client_factory(_mutable_models_handler(state))
            first = (await client.post(f"/api/v1/providers/{pid}/models/sync")).json()
            assert first["added"] == 2 and first["removed"] == 0

            state["ids"] = ["m-a"]
            second = (await client.post(f"/api/v1/providers/{pid}/models/sync")).json()
            assert second["marked_unavailable"] == 1
            assert second["removed"] == 0
            assert second["total_stored"] == 2

            registry = (await client.get(f"/api/v1/providers/{pid}/model-registry")).json()
            rows = {r["model_id"]: r["is_available"] for r in registry}
            assert rows == {"m-a": True, "m-b": False}
        finally:
            await client.delete(f"/api/v1/providers/{pid}")


@pytest.mark.asyncio
async def test_sync_prune_deletes_vanished_models():
    """prune=true removes rows the provider no longer reports."""
    state = {"ids": ["m-a", "m-b"]}
    async with _client() as client:
        provider = await _create_provider(client, "prune-provider")
        pid = provider["id"]
        try:
            from app.engine import provider_probe as pp

            pp.httpx.AsyncClient = _mock_client_factory(_mutable_models_handler(state))
            await client.post(f"/api/v1/providers/{pid}/models/sync")

            state["ids"] = ["m-a"]
            pruned = (
                await client.post(f"/api/v1/providers/{pid}/models/sync?prune=true")
            ).json()
            assert pruned["removed"] == 1
            assert pruned["total_stored"] == 1

            registry = (await client.get(f"/api/v1/providers/{pid}/model-registry")).json()
            assert {r["model_id"] for r in registry} == {"m-a"}
        finally:
            await client.delete(f"/api/v1/providers/{pid}")


@pytest.mark.asyncio
async def test_sync_prune_keeps_the_default_model():
    """The current default is never pruned, even if it vanished upstream."""
    state = {"ids": ["m-a", "m-b"]}
    async with _client() as client:
        provider = await _create_provider(client, "prune-keeps-default")
        pid = provider["id"]
        try:
            from app.engine import provider_probe as pp

            pp.httpx.AsyncClient = _mock_client_factory(_mutable_models_handler(state))
            await client.post(f"/api/v1/providers/{pid}/models/sync")
            await client.put(
                f"/api/v1/providers/{pid}/default-model", json={"model_id": "m-b"}
            )

            state["ids"] = ["m-a"]
            pruned = (
                await client.post(f"/api/v1/providers/{pid}/models/sync?prune=true")
            ).json()
            assert pruned["removed"] == 0
            registry = (await client.get(f"/api/v1/providers/{pid}/model-registry")).json()
            assert "m-b" in {r["model_id"] for r in registry}
            refreshed = (await client.get(f"/api/v1/providers/{pid}")).json()
            assert refreshed["default_model"] == "m-b"
        finally:
            await client.delete(f"/api/v1/providers/{pid}")


@pytest.mark.asyncio
async def test_sync_prune_survives_failed_discovery(monkeypatch):
    """A provider outage must never wipe the registry, even with prune."""
    state = {"ids": ["m-a"]}
    async with _client() as client:
        provider = await _create_provider(client, "prune-outage-provider")
        pid = provider["id"]
        try:
            from app.engine import provider_probe as pp

            pp.httpx.AsyncClient = _mock_client_factory(_mutable_models_handler(state))
            await client.post(f"/api/v1/providers/{pid}/models/sync")

            def boom(request: httpx.Request) -> httpx.Response:
                raise httpx.ConnectError("down", request=request)

            pp.httpx.AsyncClient = _mock_client_factory(boom)
            result = (
                await client.post(f"/api/v1/providers/{pid}/models/sync?prune=true")
            ).json()
            assert result["ok"] is False
            assert result["removed"] == 0
            registry = (await client.get(f"/api/v1/providers/{pid}/model-registry")).json()
            assert {r["model_id"] for r in registry} == {"m-a"}
        finally:
            await client.delete(f"/api/v1/providers/{pid}")


@pytest.mark.asyncio
async def test_delete_single_model_and_protects_default(stub_network):
    async with _client() as client:
        provider = await _create_provider(client, "delete-single-provider")
        pid = provider["id"]
        try:
            await client.post(f"/api/v1/providers/{pid}/models/sync")
            default = (await client.get(f"/api/v1/providers/{pid}")).json()["default_model"]
            other = "fake-large" if default == "fake-small" else "fake-small"

            # The auto-picked default is protected
            resp = await client.delete(f"/api/v1/providers/{pid}/models/{default}")
            assert resp.status_code == 409

            # The non-default model can be removed
            resp = await client.delete(f"/api/v1/providers/{pid}/models/{other}")
            assert resp.status_code == 204
            registry = (await client.get(f"/api/v1/providers/{pid}/model-registry")).json()
            assert {r["model_id"] for r in registry} == {default}

            # Missing model -> 404
            assert (
                await client.delete(f"/api/v1/providers/{pid}/models/nope")
            ).status_code == 404
        finally:
            await client.delete(f"/api/v1/providers/{pid}")


@pytest.mark.asyncio
async def test_prune_unavailable_endpoint():
    state = {"ids": ["m-a", "m-b"]}
    async with _client() as client:
        provider = await _create_provider(client, "prune-unavailable-provider")
        pid = provider["id"]
        try:
            from app.engine import provider_probe as pp

            pp.httpx.AsyncClient = _mock_client_factory(_mutable_models_handler(state))
            await client.post(f"/api/v1/providers/{pid}/models/sync")

            state["ids"] = ["m-a"]
            await client.post(f"/api/v1/providers/{pid}/models/sync")  # marks m-b unavailable

            pruned = (await client.post(f"/api/v1/providers/{pid}/models/prune")).json()
            assert pruned["removed"] == 1
            registry = (await client.get(f"/api/v1/providers/{pid}/model-registry")).json()
            assert {r["model_id"] for r in registry} == {"m-a"}
        finally:
            await client.delete(f"/api/v1/providers/{pid}")


@pytest.mark.asyncio
async def test_sync_preserves_operator_default_even_without_row_flag():
    """provider.default_model is the source of truth across syncs."""
    state = {"ids": ["m-a", "m-b", "m-c"]}
    async with _client() as client:
        provider = await _create_provider(client, "preserve-default-provider")
        pid = provider["id"]
        try:
            from app.engine import provider_probe as pp

            pp.httpx.AsyncClient = _mock_client_factory(_mutable_models_handler(state))
            await client.post(f"/api/v1/providers/{pid}/models/sync")

            # Operator picks a non-first model.
            await client.put(
                f"/api/v1/providers/{pid}/default-model", json={"model_id": "m-c"}
            )

            # A later sync (no pruning, list unchanged) must keep that choice.
            await client.post(f"/api/v1/providers/{pid}/models/sync")
            refreshed = (await client.get(f"/api/v1/providers/{pid}")).json()
            assert refreshed["default_model"] == "m-c"

            registry = (await client.get(f"/api/v1/providers/{pid}/model-registry")).json()
            defaults = [r["model_id"] for r in registry if r["is_default"]]
            assert defaults == ["m-c"]
        finally:
            await client.delete(f"/api/v1/providers/{pid}")
