"""Tests for the AI chat console.

The LLM client is faked so the suite never hits a real provider: only the
streaming plumbing, model registry lookup and error handling are exercised.
"""

import json
from typing import Any, AsyncIterator, Dict, List

import pytest
from httpx import AsyncClient

from app.api.v1 import chat as chat_module


def _client() -> AsyncClient:
    from tests.conftest import make_client

    return make_client(authenticated=True)


class _FakeChunk:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeStreamingLLM:
    """Yields a fixed set of chunks; optionally raises to test error paths."""

    def __init__(self, chunks: List[str], fail: str | None = None) -> None:
        self._chunks = chunks
        self._fail = fail

    async def astream(self, _messages: List[Dict[str, Any]]) -> AsyncIterator[_FakeChunk]:
        if self._fail:
            raise RuntimeError(self._fail)
        for chunk in self._chunks:
            yield _FakeChunk(chunk)


def _parse_sse(raw: str) -> List[Dict[str, Any]]:
    """Turn an SSE body into a list of {event, data} dicts."""
    events: List[Dict[str, Any]] = []
    for frame in raw.split("\n\n"):
        if not frame.strip():
            continue
        event = "message"
        data_lines: List[str] = []
        for line in frame.splitlines():
            if line.startswith("event:"):
                event = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:") :].strip())
        if data_lines:
            events.append({"event": event, "data": json.loads("\n".join(data_lines))})
    return events


async def _create_provider_with_models(client: AsyncClient, name: str) -> str:
    """Register a provider, then fake a registry of two models directly."""
    # Import here so the DB session helper is available in test context.
    from app.core.database import AsyncSessionLocal
    from app.models.provider_model import ProviderModel
    import uuid as _uuid

    resp = await client.post(
        "/api/v1/providers",
        json={
            "name": name,
            "provider_type": "custom",
            "base_url": "http://stub.local/v1",
            "api_key": "sk-stub",
            "is_active": True,
        },
    )
    assert resp.status_code == 201, resp.text
    pid = resp.json()["id"]

    async with AsyncSessionLocal() as db:
        db.add(
            ProviderModel(
                provider_id=_uuid.UUID(pid),
                model_id="fake-small",
                display_name="Fake Small",
                is_available=True,
                is_default=True,
            )
        )
        db.add(
            ProviderModel(
                provider_id=_uuid.UUID(pid),
                model_id="fake-large",
                display_name="Fake Large",
                is_available=True,
            )
        )
        await db.commit()
    return pid


@pytest.mark.asyncio
async def test_chat_models_lists_registry(monkeypatch):
    async with _client() as client:
        pid = await _create_provider_with_models(client, "chat-models-provider")
        try:
            resp = await client.get("/api/v1/chat/models")
            assert resp.status_code == 200
            models = resp.json()["models"]
            mine = [m for m in models if m["provider_id"] == pid]
            assert {m["model_id"] for m in mine} == {"fake-small", "fake-large"}
            # Default first in the ordering.
            assert mine[0]["model_id"] == "fake-small"
            assert mine[0]["is_default"] is True
        finally:
            await client.delete(f"/api/v1/providers/{pid}")


@pytest.mark.asyncio
async def test_chat_models_includes_default_model_without_registry(monkeypatch):
    """A provider only synced at registration still appears via default_model."""
    async with _client() as client:
        resp = await client.post(
            "/api/v1/providers",
            json={
                "name": "default-only-provider",
                "provider_type": "custom",
                "base_url": "http://stub.local/v1",
                "api_key": "sk-stub",
                "is_active": True,
                "default_model": "solo-model",
            },
        )
        pid = resp.json()["id"]
        try:
            models = (await client.get("/api/v1/chat/models")).json()["models"]
            mine = [m for m in models if m["provider_id"] == pid]
            assert [m["model_id"] for m in mine] == ["solo-model"]
        finally:
            await client.delete(f"/api/v1/providers/{pid}")


@pytest.mark.asyncio
async def test_chat_completion_streams_tokens(monkeypatch):
    monkeypatch.setattr(
        chat_module,
        "create_llm_client",
        lambda *a, **k: _FakeStreamingLLM(["Hello", ", ", "world!"]),
    )
    async with _client() as client:
        pid = await _create_provider_with_models(client, "chat-stream-provider")
        try:
            resp = await client.post(
                "/api/v1/chat/completions",
                json={
                    "provider_id": pid,
                    "model_id": "fake-small",
                    "messages": [{"role": "user", "content": "hi"}],
                },
            )
            assert resp.status_code == 200
            events = _parse_sse(resp.text)
            kinds = [e["event"] for e in events]
            assert kinds[0] == "start"
            assert kinds[-1] == "done"
            tokens = "".join(e["data"]["text"] for e in events if e["event"] == "token")
            assert tokens == "Hello, world!"
            assert events[-1]["data"]["content"] == "Hello, world!"
        finally:
            await client.delete(f"/api/v1/providers/{pid}")


@pytest.mark.asyncio
async def test_chat_completion_rejects_unknown_model(monkeypatch):
    monkeypatch.setattr(chat_module, "create_llm_client", lambda *a, **k: _FakeStreamingLLM(["x"]))
    async with _client() as client:
        pid = await _create_provider_with_models(client, "chat-unknown-provider")
        try:
            resp = await client.post(
                "/api/v1/chat/completions",
                json={
                    "provider_id": pid,
                    "model_id": "does-not-exist",
                    "messages": [{"role": "user", "content": "hi"}],
                },
            )
            assert resp.status_code == 422
            assert "not registered" in resp.json()["detail"]
        finally:
            await client.delete(f"/api/v1/providers/{pid}")


@pytest.mark.asyncio
async def test_chat_completion_reports_upstream_error(monkeypatch):
    monkeypatch.setattr(
        chat_module,
        "create_llm_client",
        lambda *a, **k: _FakeStreamingLLM([], fail="quota exhausted"),
    )
    async with _client() as client:
        pid = await _create_provider_with_models(client, "chat-error-provider")
        try:
            resp = await client.post(
                "/api/v1/chat/completions",
                json={
                    "provider_id": pid,
                    "model_id": "fake-small",
                    "messages": [{"role": "user", "content": "hi"}],
                },
            )
            assert resp.status_code == 200
            events = _parse_sse(resp.text)
            assert any(e["event"] == "error" for e in events)
            err = next(e for e in events if e["event"] == "error")
            assert "quota exhausted" in err["data"]["message"]
        finally:
            await client.delete(f"/api/v1/providers/{pid}")


@pytest.mark.asyncio
async def test_chat_completion_requires_existing_provider(monkeypatch):
    monkeypatch.setattr(chat_module, "create_llm_client", lambda *a, **k: _FakeStreamingLLM(["x"]))
    async with _client() as client:
        resp = await client.post(
            "/api/v1/chat/completions",
            json={
                "provider_id": "00000000-0000-0000-0000-000000000000",
                "model_id": "whatever",
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
        assert resp.status_code == 404
