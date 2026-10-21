# Omnigensi — Mobile & Web API Contract

This document is the integration contract for any client (web UI or the mobile
app). It describes how to bootstrap, talk to the API and stream execution
telemetry without reading backend source.

Everything below is versioned under `/api/v1` unless stated otherwise.

---

## 1. Bootstrapping a client

Call this **once at startup** before anything else:

```
GET /api/v1/config
```

```json
{
  "service": "omnigensi-backend",
  "version": "2.0.0",
  "api_version": "v1",
  "api_base_path": "/api/v1",
  "base_url": "http://192.168.1.10:8123",
  "docs_url": "http://192.168.1.10:8123/docs",
  "openapi_url": "http://192.168.1.10:8123/openapi.json",
  "streaming": {
    "path_template": "/api/v1/executions/{execution_id}/stream",
    "content_type": "text/event-stream",
    "events": ["connected", "agent_start", "token_chunk", "review_result",
               "supervisor_directive", "device_approval_required",
               "device_file_write", "tool_approval_response",
               "workflow_complete", "workflow_failed"]
  },
  "pagination": { "params": ["limit", "offset"], "default_limit": 50, "max_limit": 200 },
  "features": {
    "providers": true, "agents": true, "workflows": true, "executions": true,
    "execution_streaming": true, "execution_cancel": true, "tool_approval": true,
    "mcp_servers": true, "file_download": true, "file_upload": false
  },
  "limits": { "executions_page_size": 50, "max_page_size": 200 }
}
```

Use `base_url` (not a hardcoded `localhost`) so the same build works on a
phone, a simulator and a production server. For a manual override, probe a
candidate URL with `GET /api/v1/health` and keep the first that returns 200.

> Mobile clients are not subject to CORS. The web UI is, and the backend allows
> `http://localhost:5296`, `http://127.0.0.1:5296` and any LAN address
> (`10.x`, `192.168.x`, `172.16–31.x`) on any port.

---

## 2. Health

```
GET /api/v1/health     (also available as GET /health)
```

```json
{ "status": "healthy", "service": "omnigensi-backend", "version": "2.0.0", "workspace_root": "/app/workspace" }
```

The web UI polls this every 8 seconds to render its connectivity badge.

---

## 3. Errors

**Every** failing request returns the same envelope, so clients never branch on
whether `detail` is a string or a list:

```json
{
  "success": false,
  "detail": "Agent not found",
  "code": "not_found",
  "request_id": "52f8c46cd9474ce09de0cb1a9658827a",
  "errors": null
}
```

`code` is one of `bad_request`, `unauthorized`, `forbidden`, `not_found`,
`conflict`, `validation_error`, `rate_limited`, `internal_error`.

For validation failures (HTTP 422), `detail` is the human-readable message of
the first error and `errors` holds the field-level list:

```json
{
  "success": false,
  "detail": "Field required",
  "code": "validation_error",
  "request_id": "beefd5da…",
  "errors": [{ "loc": ["body", "role"], "msg": "Field required", "type": "missing" }]
}
```

`X-Request-ID` is echoed on every response and matches `request_id` — include it
in bug reports.

---

## 4. Pagination

Collection endpoints accept `limit` (1–200, default 50) and `offset` (>= 0):

```
GET /api/v1/agents?limit=20&offset=40
```

The body stays a **bare JSON array** (backwards compatible), and the window is
described by response headers:

| Header | Meaning |
|---|---|
| `X-Total-Count` | Total items across all pages |
| `X-Limit` | Page size applied |
| `X-Offset` | Offset applied |

Use `offset += limit` until `offset + count >= X-Total-Count`.
Invalid ranges (> 200 or <= 0) return `422 validation_error`.

Applies to: `/providers`, `/agents`, `/workflows`, `/executions`.

---

## 5. Resources

| Resource | Endpoints |
|---|---|
| Providers | `GET/POST /providers`, `GET/PUT/DELETE /providers/{id}`, `GET /providers/{id}/models` |
| Agents | `GET/POST /agents`, `GET/PUT/DELETE /agents/{id}` |
| Workflows | `GET/POST /workflows`, `GET/PUT/DELETE /workflows/{id}` |
| Tools | `GET /tools` |
| MCP | `GET/POST /mcp/servers`, `GET /mcp/servers/{name}/tools`, `POST /mcp/servers/{name}/tools/{tool}/execute` |
| Files | `GET /files/{path}` |

### Provider update semantics

`PUT /providers/{id}` is a partial update. **Omit `api_key`** to keep the stored
key; send it only when rotating. `has_api_key` reports whether a key exists —
the key itself is never returned.

### MCP tool execution

`POST /mcp/servers/{name}/tools/{tool}/execute` returns the bridge payload
flat, with the status at the root:

```json
{ "status": "success", "result": { "status": "error", "message": "…" }, "message": null }
```

---

## 6. Executions and live telemetry

### Dispatch

```
POST /api/v1/workflows/{workflow_id}/execute
Content-Type: application/json

{ "task_prompt": "Design a rate limiter" }
```

Returns `202` with the full execution record. Keep `id`, then subscribe to the
stream. The alias `POST /api/v1/executions/workflows/{id}/execute` is
equivalent; prefer the `/workflows/{id}/execute` form.

### Stream (SSE)

```
GET /api/v1/executions/{execution_id}/stream
Accept: text/event-stream
```

Frames use the standard `event:` / `data:` form; `data` is always JSON.

| Event | Key fields |
|---|---|
| `connected` | `execution_id`, `timestamp` |
| `agent_start` | `node_id`, `agent_name` |
| `token_chunk` | `node_id`, `agent_name`, `chunk` |
| `review_result` | `is_approved`, `feedback`, `revision_count` |
| `supervisor_directive` | `agent_name` |
| `device_approval_required` | `tool_call_id`, `tool_name`, `tool_args`, `agent_name` |
| `device_file_write` | `filename`, `filepath`, `content_base64`, `mime_type`, `size_bytes` |
| `tool_approval_response` | `tool_call_id`, `approved`, `notes` |
| `workflow_complete` | `final_output`, `generated_files`, `total_tokens`, `estimated_cost_usd` |
| `workflow_failed` | `status`, `error` |

Notes for native clients, which have no `EventSource`:

- Parse the stream manually (or with an SSE library) over a long-lived HTTP
  connection. Do **not** buffer the whole response.
- The server sends `: ping` comments while idle — ignore lines starting with `:`.
- The stream closes after `workflow_complete` / `workflow_failed`. Implement
  your own reconnect with backoff, and re-fetch `GET /executions/{id}` on
  reconnect to rehydrate state (the stream has no replay/`Last-Event-ID`).
- If the execution already finished, the stream replays a single terminal event,
  so subscribing after the fact is always safe.

### Human-in-the-loop approval

When `device_approval_required` arrives, the run is paused. Reply with:

```
POST /api/v1/executions/{execution_id}/approve-tool
{ "tool_call_id": "…", "approved": true, "notes": "optional" }
```

### Cancel

```
POST /api/v1/executions/{execution_id}/cancel
→ { "success": true, "status": "cancelled", "message": "Execution cancelled successfully" }
```

Cancelling an already-finished run is not an error; it returns
`{"status": "ok", "message": "Execution already completed"}`.

---

## 7. Downloading generated artifacts

`generated_files` entries and `device_file_write` events carry both `filename`
and `filepath`. Fetch with either form:

```
GET /api/v1/files/report.md
GET /api/v1/files//app/workspace/report.md     ← tool-emitted absolute filepath
```

- The response sets `Content-Disposition: attachment` and a real content type
  (PDF, DOCX, Markdown), so mobile clients can hand it to the OS viewer.
- Paths escaping the workspace return `400 bad_request`.
- No upload endpoint exists yet (`features.file_upload` is `false`).

On iOS/Android there is no File System Access API — always use this endpoint
instead of writing to the device filesystem.

---

## 8. Feature parity matrix

| Capability | Web UI | API | Mobile client |
|---|---|---|---|
| Bootstrap config | — | `GET /config` | **required at startup** |
| Provider CRUD + edit/toggle | ✅ | ✅ | ✅ |
| Provider model discovery | ✅ | ✅ | ✅ |
| Agent CRUD | ✅ | ✅ | ✅ |
| Workflow CRUD | ✅ | ✅ | ✅ |
| Execute + SSE telemetry | ✅ | ✅ | implement SSE manually |
| Cancel execution | ✅ | ✅ | ✅ |
| HITL tool approval | ✅ | ✅ | ✅ |
| MCP list/register/tools | ✅ | ✅ | ✅ |
| Artifact download | ✅ (browser) | ✅ | **use `/files`** |
| Local disk write | Chromium only | n/a | not supported by design |
| Pagination | ✅ | ✅ | ✅ |
| Uniform errors | ✅ | ✅ | ✅ |
| Auth / multi-tenant | ❌ | ❌ | not implemented |
