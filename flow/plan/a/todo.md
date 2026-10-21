# Engineering Roadmap & Actionable Task List (TODO)
**Proyek:** Omnigesi // Dynamic Multi-Agent AIaaS Platform  
**Stack:** FastAPI + LangGraph + SvelteKit 5 + TailwindCSS (Retro Cyberpunk Blue UI)

---

## Phase 1: Inisialisasi Monorepo, Docker & Infrastruktur Dasar
- [x] Buat struktur direktori utama: `backend/`, `frontend/`, dan `docker/`.
- [x] Buat file `docker-compose.yml` yang mencakup service `postgres:16-alpine`, `redis:7-alpine`, `backend`, dan `frontend`.
- [x] Inisialisasi proyek Python di `backend/` menggunakan `venv` (Python 3.12+).
- [x] Instal dependensi utama backend:
  - `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`
  - `sqlalchemy[asyncio]`, `asyncpg`, `alembic`
  - `cryptography`, `redis`, `httpx`
  - `langgraph`, `langchain-core`, `langchain-openai`
  - `python-docx`, `reportlab`, `markdown`
- [x] Inisialisasi proyek SvelteKit di `frontend/` menggunakan `pnpm` (Svelte 5 Runes, TypeScript) dan instal `tailwindcss`, `lucide-svelte`, `@xyflow/svelte`, `marked`.
- [x] Buat file `.env.example` di `backend/` dan `frontend/` (berisi `DATABASE_URL`, `REDIS_URL`, `ENCRYPTION_KEY`, `WORKSPACE_ROOT`).

---

## Phase 2: Database Layer & Multi-Provider / Omnirouter Vault (Backend)
- [x] Konfigurasi `backend/app/core/database.py` untuk koneksi `AsyncEngine` dan `async_sessionmaker` ke PostgreSQL.
- [x] Buat utilitas `backend/app/core/security.py`:
  - [x] Fungsi `encrypt_api_key(plain_key: str) -> str` dan `decrypt_api_key(enc_key: str) -> str` menggunakan `cryptography.fernet.Fernet`.
  - [x] Fungsi `sanitize_workspace_path(relative_path: str) -> Path` untuk mencegah serangan *Directory Traversal* (`../`).
- [x] Buat model SQLAlchemy dan migrasi Alembic untuk tabel:
  - [x] `llm_providers`
  - [x] `agent_templates`
  - [x] `workflows`
  - [x] `workflow_executions`
- [x] Buat modul `backend/app/engine/llm_factory.py`:
  - [x] Fungsi `create_llm_client(provider: LLMProvider, model_name: str, temperature: float, max_tokens: int)` yang mengembalikan objek `ChatOpenAI` yang diarahkan ke `base_url` provider (mendukung OpenRouter, LiteLLM, OpenAI, maupun Ollama).
- [x] Buat router API `backend/app/api/v1/providers.py`:
  - [x] `POST /api/v1/providers` (Simpan provider dengan API key terenkripsi).
  - [x] `GET /api/v1/providers` (List semua provider tanpa mengekspos API key asli).
  - [x] `GET /api/v1/providers/{id}/models` (Request menggunakan `httpx` ke `{base_url}/models` milik Omnirouter untuk mengambil daftar model dinamis).

---

## Phase 3: Local Device Interaction & Document Tools Engine (Backend)
- [x] Buat modul `backend/app/engine/tool_registry.py` yang mendefinisikan fitur interaksi perangkat menggunakan dekorator `@tool` LangChain:
  - [x] `create_markdown_document(filename: str, content: str)`: Menulis file `.md` ke dalam folder `workspace/` dan mengembalikan metadata file (nama, path, ukuran, dan konten base64/teks untuk disinkronkan ke browser klien).
  - [x] `create_word_document(filename: str, title: str, sections: list[dict])`: Menggunakan `python-docx` untuk membuat file `.docx` terstruktur lengkap dengan judul, subjudul, dan paragraf, lalu mengembalikan payload base64 untuk disinkronkan ke perangkat pengguna.
  - [x] `create_pdf_document(filename: str, title: str, body_text: str)`: Menggunakan `reportlab` untuk men-generate dokumen `.pdf` dan mengembalikan payload base64.
  - [x] `read_local_workspace_file(filename: str)`: Membaca isi file teks/kode dari direktori kerja yang diizinkan agar Agent bisa menganalisis file milik pengguna.
  - [x] `list_local_workspace_files(subdirectory: str = ".")`: Menampilkan pohon direktori lokal kepada Agent.
- [x] Buat dictionary `DEVICE_TOOL_MAP` yang memetakan string ID fitur ke fungsi `@tool` terkait.
- [x] Buat endpoint `GET /api/v1/tools` yang mengembalikan daftar fitur perangkat beserta nama, deskripsi, dan ikonnya agar dapat dirender sebagai *checkbox* di UI SvelteKit.

---

## Phase 4: Dynamic Agent Studio & LangGraph Compiler (Backend)
- [x] Buat router API `backend/app/api/v1/agents.py`:
  - [x] Endpoint CRUD lengkap (`GET`, `POST`, `PUT`, `DELETE`) untuk tabel `agent_templates`.
  - [x] Validasi bahwa setiap `tools_config` yang dikirim user terdaftar di dalam `DEVICE_TOOL_MAP`.
- [x] Buat script *seeder* awal untuk 4 agen contoh:
  1. `CYPHER-01 // Deep Researcher` (Node Type: `worker`, Model: via Omnirouter).
  2. `SCRIBE-02 // Technical Architect Writer` (Node Type: `worker`).
  3. `OVERSEER-03 // Strict QA Reviewer` (Node Type: `reviewer` dengan output JSON `is_approved` & `feedback`).
  4. `FABRICATOR-04 // Device Document Publisher` (Node Type: `worker`, Tools: `["create_markdown_document", "create_word_document", "create_pdf_document"]`).
- [x] Bangun mesin kompilasi graf dinamis di `backend/app/engine/compiler.py`:
  - [x] Buat fungsi `build_dynamic_agent_node(agent_cfg, provider_cfg, event_publisher)`:
    - [x] Merakit System Prompt dengan format CrewAI (`Role`, `Goal`, `Backstory`).
    - [x] Jika `agent_cfg.node_type == "reviewer"`, gunakan `.with_structured_output(ReviewDecision)` (disertai fallback JSON parser jika model di Omnirouter tidak mendukung native structured output).
    - [x] Jika `agent_cfg.tools_config` tidak kosong, ikat tool menggunakan `llm.bind_tools(selected_tools)` dan jalankan eksekusi tool secara otomatis, lalu pancarkan event `device_file_generated` ke Redis Pub/Sub.
  - [x] Buat fungsi `compile_workflow_graph(workflow_schema, db_session)`:
    - [x] Instansiasi `StateGraph(DynamicTeamState)`.
    - [x] Loop seluruh `nodes` dari JSON database dan panggil `workflow.add_node()`.
    - [x] Loop seluruh `edges` dari JSON database: pasang `add_edge()` untuk jalur biasa, dan `add_conditional_edges()` untuk node bertipe `reviewer` (cek `is_approved` dan batas `max_revisions`).
    - [x] Return hasil `workflow.compile()`.

---

## Phase 5: Asynchronous Execution & Real-Time SSE Streaming (Backend)
- [x] Buat router API `backend/app/api/v1/workflows.py` untuk menyimpan dan mengambil skema rakitan Multi-Agent.
- [x] Buat router API `backend/app/api/v1/executions.py`:
  - [x] `POST /api/v1/workflows/{id}/execute`: Membuat record di `workflow_executions` dengan status `running`, menjalankan kompilasi LangGraph di *background task*, dan langsung mengembalikan `execution_id`.
  - [x] Di dalam *background runner*, gunakan `async for event in compiled_graph.astream_events(...)` untuk mempublikasikan setiap langkah ke channel Redis `execution:{execution_id}`:
    - Event `agent_start`: Nama agen, peran, dan model yang digunakan.
    - Event `token_chunk`: Streaming teks yang sedang diketik oleh agen.
    - Event `review_result`: Keputusan Reviewer (`APPROVED` atau `REJECTED` beserta *feedback* revisi).
    - Event `device_file_write`: Berisi `filename`, `mime_type`, dan `content_base64` saat agen mengeksekusi tool pembuatan dokumen.
    - Event `workflow_complete`: Hasil akhir dan total kalkulasi token.
  - [x] `GET /api/v1/executions/{execution_id}/stream`: Endpoint `StreamingResponse` (`text/event-stream`) yang berlangganan ke channel Redis `execution:{execution_id}` dan meneruskannya ke SvelteKit.

---

## Phase 6: Desain Sistem "Retro Cyberpunk Blue" & Theme Switcher (Frontend)
- [x] Konfigurasi `frontend/src/app.css` dengan variabel CSS untuk dua tema:
  - [x] `:root[data-theme="dark"]` (**Cyber-Abyss Mode**): Background `#040814`, Surface `#0A1228`, Neon Cyan `#00F0FF`, Hyper Cobalt `#0066FF`, Glow Shadows, dan opsi CRT Scanline Overlay.
  - [x] `:root[data-theme="light"]` (**Mecha-Lab Daylight Mode**): Background `#EBF3FA`, Surface `#FFFFFF`, High-Voltage Cobalt `#0048E5`, Deep Naval Ink `#071327`, dan Hard Brutalist Offset Shadows (`4px 4px 0px #0048E5`).
- [x] Import font Google di `app.html`: `Orbitron` (untuk judul HUD), `Space Grotesk` (untuk body), dan `JetBrains Mono` (untuk log terminal & metrik).
- [x] Buat store Svelte 5 `frontend/src/lib/stores/theme.svelte.ts`:
  - [x] State reaktif `mode = $state<'dark' | 'light'>('dark')` dan `crtScanlines = $state<boolean>(true)`.
  - [x] Fungsi `toggleTheme()` yang memperbarui atribut `document.documentElement.setAttribute('data-theme', mode)` dan menyimpan preferensi ke `localStorage`.
- [x] Buat komponen UI dasar bergaya Retro Cyberpunk:
  - [x] `CyberCard.svelte`: Kontainer dengan sudut terpotong (`clip-path`), aksen garis siku di pojok kartu, dan header berlabel kode teknis (misal: `SYS.MODULE // 01`).
  - [x] `CyberButton.svelte`: Tombol poligon dengan efek bunyi klik visual, border menyala, dan variasi warna (`primary-cyan`, `cobalt`, `danger-crimson`).
  - [x] `ThemeToggle.svelte`: Sakelar bergaya kokpit di Topbar untuk berpindah antara **DARK [ABYSS]** dan **LIGHT [DAYLIGHT]** serta tombol on/off efek **CRT**.

---

## Phase 7: Local Device Bridge Service di SvelteKit (Frontend)
- [x] Buat modul `frontend/src/lib/stores/deviceBridge.svelte.ts` menggunakan Svelte 5 Runes:
  - [x] State `directoryHandle = $state<FileSystemDirectoryHandle | null>(null)` dan `mountedFolderName = $state<string | null>(null)`.
  - [x] State `autoWriteEnabled = $state<boolean>(true)` dan `writeHistory = $state<Array<{filename: string, timestamp: string, status: string}>>([])`.
  - [x] Method `mountLocalDirectory()`: Memanggil `window.showDirectoryPicker({ mode: 'readwrite' })` agar pengguna memilih folder target di komputer mereka.
  - [x] Method `saveAgentFileToDevice(filename: string, base64Data: string)`: Mengonversi base64 menjadi `Uint8Array`/`Blob`, lalu menulisnya langsung ke *hard drive* lokal menggunakan `directoryHandle.getFileHandle(filename, { create: true })` dan `createWritable()`.
  - [x] Fallback otomatis: Jika browser pengguna tidak mendukung File System Access API (atau folder belum di-*mount*), sediakan *trigger download* langsung ke perangkat.

---

## Phase 8: Halaman Studio & Visual Workflow Builder (Frontend)
- [x] Bangun **Layout Utama (`src/routes/+layout.svelte`)**:
  - [x] Sidebar navigasi bergaya terminal militer/cyberdeck (`[01] COMMAND CENTER`, `[02] OMNIROUTER VAULT`, `[03] AGENT STUDIO`, `[04] GRAPH COMPILER`, `[05] EXECUTION DECK`).
  - [x] Topbar dengan status koneksi backend, indikator status `LOCAL DRIVE: MOUNTED / DISCONNECTED`, dan `ThemeToggle`.
- [x] Bangun **Halaman Omnirouter & Provider Vault (`src/routes/providers/+page.svelte`)**:
  - [x] Form input tambah provider baru (Nama, Tipe Provider, Base URL seperti `https://openrouter.ai/api/v1`, API Key).
  - [x] Tombol `[SYNC MODELS]` untuk menguji koneksi dan menampilkan daftar model yang berhasil ditarik dari provider tersebut.
- [x] Bangun **Halaman Dynamic Agent Studio (`src/routes/agents/+page.svelte`)**:
  - [x] Grid kartu daftar Agent yang sudah dibuat, lengkap dengan badge tipe node (`WORKER` / `REVIEWER`), model LLM yang dipakai, dan ikon fitur hardware yang aktif.
  - [x] Modal/Drawer **Create & Edit Agent**:
    - [x] Input `Name`, `Role`, `Goal`, dan `Backstory`.
    - [x] Pemilih `Provider` dan *searchable combobox* `Model Name` (dinamis dari Omnirouter).
    - [x] Pemilih `Node Behavior` (`Worker` vs `Reviewer`).
    - [x] Panel **Hardware & Document Capabilities**: Daftar *toggle switch* untuk mengaktifkan fitur `Markdown Generator (.md)`, `Word Document Builder (.docx)`, `PDF Report Generator (.pdf)`, dan `Local Workspace Reader`.
- [x] Bangun **Halaman Workflow Builder (`src/routes/workflows/+page.svelte`)**:
  - [x] Antarmuka perakitan urutan Agent (bisa menambah Agent ke-1, ke-2, ke-3, hingga ke-N dari daftar template Agent).
  - [x] Konfigurasi *Conditional Edge* pada Agent bertipe `Reviewer`: menentukan ke Agent mana tugas dikembalikan saat status `REJECTED`, serta input angka `Max Revisions`.

---

## Phase 9: Live Execution Playground & Integrasi End-to-End
- [x] Bangun **Halaman Execution Playground (`src/routes/playground/+page.svelte`)**:
  - [x] **Panel Kontrol Kiri:** Dropdown pemilih Workflow, Textarea input `Task Prompt`, dan panel kontrol **Local Hardware Bridge** (Tombol `[MOUNT LOCAL FOLDER]` untuk memilih direktori di PC pengguna).
  - [x] **Panel Tengah (Live Cyber-Telemetry & Agent Stepper):**
    - [x] Visualisasi node Agent yang menyala berurutan mengikuti event SSE `agent_start`.
    - [x] Layar terminal monospace yang melakukan *live streaming* teks/pemikiran agen secara *real-time*.
    - [x] Alert visual berwarna kuning/merah ketika Agent `Reviewer` menolak draf dan memicu siklus revisi kembali ke `Worker`.
  - [x] **Panel Kanan (Output & Device Artifacts):**
    - [x] Tab 1: Hasil akhir (*Final Output*) yang dirender dalam format Markdown bersih.
    - [x] Tab 2: **Hardware Sync Log** yang menampilkan daftar dokumen (`.md`, `.docx`, `.pdf`) yang telah dibuat oleh Agent dan otomatis tertulis ke dalam folder lokal komputer pengguna.
- [x] Lakukan pengujian menyeluruh (*End-to-End Test*):
  - [x] Uji coba tambah Provider OpenRouter/LiteLLM.
  - [x] Uji coba buat 4 Agent berbeda dengan model berbeda dan aktifkan tool pembuat dokumen pada Agent terakhir.
  - [x] Mount folder lokal di browser, jalankan workflow, pastikan siklus revisi berjalan jika draf kurang lengkap, dan pastikan file `.md` serta `.docx` otomatis muncul di *hard drive* lokal saat eksekusi selesai.
  - [x] Verifikasi tampilan kontras, keterbacaan teks, dan estetika Retro Cyberpunk Blue pada **Dark Mode** maupun **Light Mode**.

---

## Phase 10: Model Context Protocol (MCP), Supervisor Pattern & Human-in-the-Loop Security (Completed)
- [x] **Model Context Protocol (MCP SDK v2.3.0) Integration:**
  - [x] Implementasi `backend/app/engine/mcp_bridge.py` dengan dukungan transport stdio & SSE, auto-discovery tools, dan dynamic LangChain `StructuredTool` adapter.
  - [x] Registrasi built-in MCP server (`filesystem-mcp`, `memory-mcp`) dan integrasi ke `AVAILABLE_TOOLS_METADATA` serta `DEVICE_TOOL_MAP`.
  - [x] Endpoint REST API `backend/app/api/v1/mcp.py` (`GET/POST /api/v1/mcp/servers`, `GET /api/v1/mcp/servers/{name}/tools`, `POST /api/v1/mcp/servers/{name}/tools/{tool}/execute`).
- [x] **Supervisor Agent Orchestration Pattern:**
  - [x] Implementasi dedicated execution branch untuk `node_type == "supervisor"` pada `backend/app/engine/compiler.py`.
  - [x] System prompt executive directive synthesis dan pemancaran event `supervisor_directive`.
  - [x] Styling visual ungu neon khusus untuk Supervisor Agent Node di Xyflow canvas.
- [x] **Human-in-the-Loop (HITL) Device Authorization Gate:**
  - [x] Redis Pub/Sub gating `device_approval_required` saat agent dengan `require_device_approval=True` memanggil tool penulisan file.
  - [x] Komunikasi dua arah dengan endpoint `POST /api/v1/executions/{id}/approve-tool`.
  - [x] Modal interaktif bergaya Retro Cyberpunk Blue di `frontend/src/routes/playground/+page.svelte` dengan tombol `[AUTHORIZE WRITE]` dan `[REJECT & ABORT]`.
- [x] **Multi-Model Token Cost Estimator Calculator:**
  - [x] Modul `backend/app/engine/token_cost.py` yang memetakan rate per 1M token untuk OpenAI, Anthropic, DeepSeek, Meta Llama, Google Gemini, Qwen, Mistral, dan Ollama.
  - [x] Kalkulasi akurat total token dan estimasi biaya USD yang tersimpan di PostgreSQL dan dipancarkan ke event `workflow_complete`.
- [x] **Verifikasi & Test Suite:**
  - [x] 19 unit & integration tests pytest lulus 100% (`tests/test_api.py`, `tests/test_tools.py`, `tests/test_security.py`, `tests/test_token_cost.py`, `tests/test_mcp.py`, `tests/test_compiler_extended.py`).
  - [x] `svelte-check` lulus dengan 0 errors dan 0 warnings.
  - [x] Production build Vite/SvelteKit sukses 100%.
