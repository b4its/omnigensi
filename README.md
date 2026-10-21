# Omnigensi — Multi-Agent AIaaS & Device Orchestrator

A dynamic multi-agent platform: design LLM providers, CrewAI-style agent
personas and LangGraph workflows in a web UI, then execute them and watch live
telemetry — including agent-generated documents written to your own machine.

The same backend powers a mobile client; the full integration contract lives in
[`docs/MOBILE_API.md`](docs/MOBILE_API.md).

---

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, SQLAlchemy async, LangGraph / LangChain, Redis (SSE transport) |
| Frontend | SvelteKit 3 (Svelte 5 runes), Tailwind v4, xyflow |
| Data | PostgreSQL 16, Redis 7 |
| Runtime | Docker Compose (dev + prod targets) |

---

## Quick start

```bash
make init      # create .env from the example
make up        # build and start the full stack
make status    # container health
```

| Service | URL |
|---|---|
| Web UI | http://localhost:5296 |
| API | http://localhost:8123 |
| API docs | http://localhost:8123/docs |
| PostgreSQL | localhost:5558 |
| Redis | localhost:6505 |

`make` on its own lists every available command (`make help`).

### Everyday commands

```bash
make logs-backend   # follow backend logs
make test           # run the backend test suite
make db-seed        # load demo providers/agents/workflows
make down           # stop the stack
```

---

## Configuration

Copy `.env.example` to `.env`. Notable variables:

| Variable | Default | Purpose |
|---|---|---|
| `ENCRYPTION_KEY` | dev key | Fernet key used to encrypt provider API keys |
| `CORS_ORIGINS` | localhost URLs | Browser origins allowed to call the API |
| `CORS_ORIGIN_REGEX` | LAN ranges | Allows phones/tablets on the same network |
| `PUBLIC_BASE_URL` | auto-detected | Absolute base URL reported by `/api/v1/config` |
| `PUBLIC_API_URL` | — | Frontend build-time API URL (e.g. `http://192.168.1.10:8123`) |

### Using the UI from a phone

Set `PUBLIC_API_URL` to your machine's LAN address, rebuild the frontend, and
open `http://<lan-ip>:5296`. Without it the UI assumes it is served from the
same origin as the API.

---

## Project layout

```
backend/            FastAPI app
  app/api/v1/       HTTP routers (providers, agents, workflows, executions, tools, mcp)
  app/engine/       LangGraph compiler, tool registry, MCP bridge, publisher
  app/core/         config, database, security, error handling
  tests/            pytest suite
frontend/           SvelteKit app
  src/lib/api.ts    single API client used by every page
  src/routes/       dashboard, providers, agents, workflows, playground
docs/MOBILE_API.md  client integration contract (web + mobile)
docker-compose.yml  dev stack
docker-compose.prod.yml  production overrides
Makefile            all operational commands
```

---

## Testing

```bash
make test        # full pytest suite inside the container
make check       # svelte-check type diagnostics
make lint        # compose validation + Python syntax check
```

Coverage includes API contracts, pagination, the uniform error envelope, CORS
policy, file-download security and full end-to-end workflow execution.

---

## Known limitations

- **No authentication.** Every endpoint is open and all data is global. Add an
  auth layer before exposing this beyond a trusted network.
- **MCP servers are in-memory.** They are lost on restart.
- **No file upload endpoint** (download only).
- **Local disk write requires the File System Access API**, i.e. a Chromium
  desktop browser. Mobile clients use the `/api/v1/files` download endpoint.
