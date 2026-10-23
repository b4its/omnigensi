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
> The UI asks for a password. The default is `123` (set `APP_PASSWORD` to
> change it).

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
| `APP_PASSWORD` | `123` | Single operator password guarding the whole instance |
| `AUTH_ENABLED` | `true` | Set `false` to disable the login gate |
| `AUTH_TOKEN_SECRET` | falls back to `ENCRYPTION_KEY` | Signing secret for session tokens |
| `AUTH_TOKEN_TTL_SECONDS` | `604800` (7 days) | Session lifetime |
| `PROVIDER_TLS_VERIFY` | `true` | Verify TLS on outbound provider calls |

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

## Naskah Studio (document editor)

`/editor` is a full word processor modelled on Microsoft Word (feature parity
with [Wordcraft](https://github.com/storytold/wordcraft)) plus the parts of
LibreOffice Writer those tools do not cover.

| Area | What it does |
|---|---|
| Ribbon | File · Home · **Format** · Insert · Design · Layout · References · Mailings · Review · View, plus contextual **Table** and **Picture** tabs |
| File | New from 5 templates, open, save, export `.docx` `.doc` `.odt` `.rtf` `.tex` `.html` `.md` `.txt`, print/PDF, document properties, crash recovery, version history |
| Home | Clipboard, Format Painter, font family/size, bold/italic/underline (incl. double), strike, sub/superscript, small caps, all caps, hidden, highlight, colour, text effects (outline/shadow/glow/emboss), character spacing/scale/position, enclosed characters, change case, clear formatting |
| Paragraph | Alignment (incl. distributed), RTL, bullets/numbering/multilevel, list styles, indent/outdent, hanging indent, line spacing, spacing before/after, keep-with-next, keep-lines, widow control, page-break-before, sort, move up/down |
| Styles | Live gallery of Word and Writer styles, custom styles created from the caret, floating styles pane |
| Insert | Cover pages, blank page, page/column/section breaks, tables (grid + quick tables + text↔table), pictures, shapes, icons, SmartArt, charts, links with named targets, bookmarks, cross-references, text boxes, WordArt, drop caps, signature lines, date/time, quick parts, symbols, equations |
| Format (Writer) | **AutoText** library, insertable fields, in-text page numbers, text frames with anchor/wrap, Fontwork, list gallery, horizontal-line gallery, column presets |
| Design | Themes, paragraph-spacing presets, watermark, page colour, page borders, dark paper |
| Layout | Page setup (paper, orientation, margins, gutter, columns, vertical alignment), line numbers, hyphenation, paragraph and arrange controls |
| References | Table of contents from live headings, table of figures, index, footnotes/endnotes with renumbering, citations (APA/MLA/Chicago/IEEE) and bibliography, captions |
| Mailings | CSV recipient list, merge fields, address block, greeting line, IF rules, record preview, merge, envelopes and labels |
| Review | Comments with **margin balloons**, track changes (accept/reject one or all), Indonesian spelling pass, thesaurus, read-aloud, accessibility inspector, word count |
| View | Read mode, navigation pane, ruler, formatting marks, single/two-page, full screen, dark mode, zoom |
| Table / Picture | Merge/split cells, repeat header, banded rows, shading, borders, distribute, auto-fit, sort, SUM/AVERAGE/COUNT/MAX/MIN formulas, table→text; resize, rotate, crop, alt text, text wrapping |
| Everywhere | Tell-Me command search (`Alt+Q`), keyboard shortcuts (`Ctrl+S/F/P/K/G`, `Ctrl+B/I/U`), autosave, crash recovery, Indonesian UI and formatters |

The document engine lives in `frontend/src/lib/editor/`: `commands`/`charFx`/
`paraFx` (formatting), `styles`, `insertBlocks`/`loBlocks` (building blocks),
`references`, `review`, `mailings`, `tableTools`, `pageSetup`/`loLayout`,
`fileFormats`/`export` (native `.docx`/`.odt` ZIP writers) and
`persistence` (autosave/versions). Units are covered by the Vitest suite.

---

## Testing

```bash
make test           # full pytest suite inside the container
make test-frontend  # Vitest unit tests for the editor libraries
make check          # svelte-check type diagnostics
make lint           # compose validation + Python syntax check
```

Coverage includes API contracts, pagination, the uniform error envelope, CORS
policy, file-download security and full end-to-end workflow execution; the
editor suite covers the formatting, reference, review, mail-merge, table and
file-format libraries plus the plain-text engine.

---

## Known limitations

- **Single shared password, no users.** `APP_PASSWORD` (default `123`) guards
  the whole instance; there are no per-user accounts, roles or audit trail.
  Rotate it from **Settings** in the UI (stored as a PBKDF2 hash) or change
  `APP_PASSWORD` and restart. Note the API is only as safe as that password
  because transport may be plain HTTP on a LAN.
- **MCP servers are in-memory.** They are lost on restart.
- **No file upload endpoint** (download only).
- **Local disk write requires the File System Access API**, i.e. a Chromium
  desktop browser. Mobile clients use the `/api/v1/files` download endpoint.
