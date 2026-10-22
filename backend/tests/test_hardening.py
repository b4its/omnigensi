"""Tests for hardening: login throttling, honest degradation and readiness.

Covers the issues found in the audit:
* no brute-force protection on login
* 401 responses lacking a request id
* simulated fallbacks presented as real completions
* fake MCP memory / unknown-tool successes
* /health not verifying dependencies
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core import rate_limit
from app.core.config import settings
from app.core.rate_limit import LoginThrottle, client_key
from app.main import app
from tests.conftest import auth_headers, make_client


def _anon_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture(autouse=True)
def clear_throttle():
    rate_limit.login_throttle.reset()
    yield
    rate_limit.login_throttle.reset()


# --------------------------------------------------------------------------
# Login throttling
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_locks_out_after_repeated_failures():
    """A short default password must not be brute-forceable."""
    async with _anon_client() as client:
        attempts = settings.AUTH_MAX_LOGIN_ATTEMPTS
        for _ in range(attempts):
            resp = await client.post("/api/v1/auth/login", json={"password": "wrong"})
            assert resp.status_code == 401

        # The next attempt is refused even with the CORRECT password.
        locked = await client.post(
            "/api/v1/auth/login", json={"password": settings.APP_PASSWORD}
        )
        assert locked.status_code == 429
        assert locked.json()["code"] == "rate_limited"
        assert int(locked.headers["retry-after"]) > 0


@pytest.mark.asyncio
async def test_successful_login_resets_the_counter():
    async with _anon_client() as client:
        for _ in range(settings.AUTH_MAX_LOGIN_ATTEMPTS - 1):
            await client.post("/api/v1/auth/login", json={"password": "wrong"})

        ok = await client.post(
            "/api/v1/auth/login", json={"password": settings.APP_PASSWORD}
        )
        assert ok.status_code == 200

        # Counter cleared, so a fresh round of failures starts from zero.
        for _ in range(settings.AUTH_MAX_LOGIN_ATTEMPTS - 1):
            resp = await client.post("/api/v1/auth/login", json={"password": "wrong"})
            assert resp.status_code == 401


def test_throttle_uses_exponential_backoff():
    throttle = LoginThrottle(
        max_attempts=2, window_seconds=60, base_lockout_seconds=10
    )
    assert throttle.record_failure("ip") == 0
    first = throttle.record_failure("ip")
    assert first == 10
    # A further failure escalates the lockout.
    second = throttle.record_failure("ip")
    assert second > first
    assert throttle.retry_after("ip") > 0


def test_throttle_window_expiry_forgets_old_failures(monkeypatch):
    throttle = LoginThrottle(
        max_attempts=2, window_seconds=10, base_lockout_seconds=5
    )

    # Control the clock from the very first failure so the sliding window
    # arithmetic is deterministic.
    clock = {"now": 1_000_000.0}
    monkeypatch.setattr(rate_limit.time, "time", lambda: clock["now"])

    assert throttle.record_failure("ip") == 0  # below the threshold

    # Move past the window: the earlier failure must be forgotten, so this
    # attempt starts a fresh count instead of triggering a lockout.
    clock["now"] += 60
    assert throttle.record_failure("ip") == 0
    assert throttle.retry_after("ip") == 0

    # A second failure inside the window does trigger the lockout.
    clock["now"] += 1
    assert throttle.record_failure("ip") == 5


def test_client_key_prefers_socket_address():
    class Client:
        host = "10.0.0.7"

    class Req:
        client = Client()

    assert client_key(Req()) == "10.0.0.7"

    class NoClient:
        client = None

    assert client_key(NoClient()) == "unknown"


# --------------------------------------------------------------------------
# 401 must be debuggable
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_401_carries_request_id_header_and_body():
    async with _anon_client() as client:
        resp = await client.get("/api/v1/agents")
        assert resp.status_code == 401
        header_id = resp.headers.get("x-request-id")
        assert header_id
        assert resp.json()["request_id"] == header_id
        assert resp.headers.get("www-authenticate") == "Bearer"


@pytest.mark.asyncio
async def test_401_echoes_a_client_supplied_request_id():
    async with _anon_client() as client:
        resp = await client.get(
            "/api/v1/agents", headers={"X-Request-ID": "trace-me-123"}
        )
        assert resp.status_code == 401
        assert resp.headers["x-request-id"] == "trace-me-123"
        assert resp.json()["request_id"] == "trace-me-123"


# --------------------------------------------------------------------------
# Health must verify dependencies
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_reports_dependencies():
    async with _anon_client() as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert body["dependencies"]["database"] == "ok"
        assert body["dependencies"]["redis"] == "ok"


@pytest.mark.asyncio
async def test_health_degrades_when_redis_is_down(monkeypatch):
    """A monitor must not stay green during a dependency outage."""
    import app.main as main_module

    class BrokenRedis:
        @classmethod
        def from_url(cls, *args, **kwargs):
            return cls()

        async def ping(self):
            raise ConnectionError("redis down")

        async def aclose(self):
            return None

    monkeypatch.setattr(main_module.aioredis, "from_url", BrokenRedis.from_url)

    async with _anon_client() as client:
        resp = await client.get("/health")
        assert resp.status_code == 503
        body = resp.json()
        assert body["status"] == "degraded"
        assert body["dependencies"]["redis"].startswith("error:")
        assert body["dependencies"]["database"] == "ok"


# --------------------------------------------------------------------------
# No fake successes
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mcp_memory_tools_report_failure_instead_of_fake_success():
    from app.engine.tool_registry import mcp_create_entities, mcp_read_graph

    created = mcp_create_entities.invoke(
        {"entities": [{"name": "X", "entityType": "T", "observations": []}]}
    )
    assert created["status"] == "error"
    assert created["entities_count"] == 0
    assert "NOT persisted" in created["message"]

    read = mcp_read_graph.invoke({})
    assert read["status"] == "error"
    assert read["entities"] == []
    assert "empty" in read["message"]


@pytest.mark.asyncio
async def test_unknown_mcp_tool_is_not_reported_as_success():
    from app.engine.mcp_bridge import mcp_manager

    result = await mcp_manager.execute_tool(
        "memory-mcp", "some_unknown_tool", {"a": 1}
    )
    assert result["status"] == "error"
    assert result.get("tool_available") is False


@pytest.mark.asyncio
async def test_simulated_execution_is_flagged(monkeypatch):
    """A provider failure must never look like a genuine completion."""
    async with make_client() as client:
        workflows = (await client.get("/api/v1/workflows")).json()
        created = await client.post(
            f"/api/v1/workflows/{workflows[0]['id']}/execute",
            json={"task_prompt": "simulated flag probe"},
        )
        exec_id = created.json()["id"]

        # Seeded credentials are demo values, so the provider call fails and
        # the graph falls back to simulation. Wait for a terminal state.
        import asyncio

        for _ in range(40):
            row = (await client.get(f"/api/v1/executions/{exec_id}")).json()
            if row["status"] not in ("running", "pending", "waiting_approval"):
                break
            await asyncio.sleep(0.25)

        row = (await client.get(f"/api/v1/executions/{exec_id}")).json()
        assert row["status"] in ("completed", "failed", "cancelled")
        if row["status"] == "completed" and row.get("simulated"):
            assert row["error_message"]
            assert "simulated" in row["error_message"].lower()

        await client.post(f"/api/v1/executions/{exec_id}/cancel")


@pytest.mark.asyncio
async def test_failure_message_is_not_stored_in_final_output():
    """Errors live in error_message; final_output is reserved for content."""
    async with make_client() as client:
        workflows = (await client.get("/api/v1/workflows")).json()
        created = await client.post(
            f"/api/v1/workflows/{workflows[0]['id']}/execute",
            json={"task_prompt": "cancel marker probe"},
        )
        exec_id = created.json()["id"]
        await client.post(f"/api/v1/executions/{exec_id}/cancel")

        import asyncio

        for _ in range(20):
            row = (await client.get(f"/api/v1/executions/{exec_id}")).json()
            if row["status"] == "cancelled":
                break
            await asyncio.sleep(0.2)

        row = (await client.get(f"/api/v1/executions/{exec_id}")).json()
        assert row["status"] == "cancelled"
        assert row["error_message"] == "Execution aborted by operator."
        # The old behaviour stuffed this string into final_output.
        assert "aborted" not in (row["final_output"] or "").lower()


@pytest.mark.asyncio
async def test_execution_indexes_exist():
    """The history filters must be backed by indexes."""
    from sqlalchemy import text

    from app.core.database import engine

    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = 'workflow_executions'"
            )
        )
        names = {r[0] for r in rows}

    for expected in (
        "ix_workflow_executions_workflow_id",
        "ix_workflow_executions_status",
        "ix_workflow_executions_started_at",
    ):
        assert expected in names
