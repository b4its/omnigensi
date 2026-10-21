# Product Requirements Document (PRD)
**Nama Proyek:** Omnigesi // Dynamic Multi-Agent AIaaS & Local Device Orchestrator  
**Versi Dokumen:** 2.0.0 (End-to-End Blueprint)  
**Tech Stack Utama:** FastAPI (Python 3.12+), LangGraph, SvelteKit (Svelte 5 Runes), TailwindCSS, PostgreSQL, Redis  
**Estetika UI/UX:** Retro Cyberpunk Blue (Dual Theme: Cyber-Abyss Dark & Mecha-Lab Light)

---

## 1. Ringkasan Eksekutif (Executive Summary)
**NEXUS-BLUE** adalah platform *AI as a Service* (AIaaS) berbasis arsitektur Multi-Agent dinamis yang memungkinkan pengguna merakit, menambah, dan mengonfigurasi agen AI tanpa batas (*unlimited custom agents*) secara langsung dari antarmuka pengguna tanpa memodifikasi kode sumber.

Platform ini menggabungkan dua paradigma utama:
1. **Role-Based Persona (CrewAI Style):** Setiap agen memiliki *Role*, *Goal*, dan *Backstory* spesifik untuk menghasilkan kualitas penalaran yang tajam.
2. **Stateful Cyclic Graph (LangGraph Engine):** Alur kerja mendukung *sequential execution* maupun *cyclic loop* (misalnya: Agent Reviewer menolak draf dan mengembalikannya ke Agent Worker untuk direvisi secara otomatis).

Selain bekerja di *cloud*, platform ini memiliki fitur **Local Device & Hardware Bridge**, di mana agen-agen AI dapat diberikan hak akses (sebagai fitur *toggleable*) untuk berinteraksi langsung dengan perangkat keras/komputer pengguna—seperti men-generate dokumen kerja (`.md`, `.docx`, `.pdf`), membaca struktur direktori proyek lokal, dan mengeksekusi *tools* lokal melalui **Web File System Access API**, **Host Volume Mounting**, maupun **Model Context Protocol (MCP)**.

---

## 2. Arsitektur Sistem & Tech Stack

### 2.1. Diagram Alur Tingkat Tinggi (High-Level Architecture)
```text
[SvelteKit 5 Frontend (Retro Cyberpunk Blue UI)]
       |  ^
       |  | (1) REST API (CRUD Providers, Agents, Workflows)
       |  | (2) SSE Stream (Real-time Agent Thoughts, Token Stream & File Payload)
       |  | (3) Web File System Access API (Direct Local Disk Read/Write)
       v  |
[FastAPI Backend & Dynamic Graph Compiler] <---> [PostgreSQL (Metadata & State History)]
       |                                   <---> [Redis (Pub/Sub SSE & Task Queue)]
       v
[Dynamic LangGraph Runtime Engine]
   ├── Node 1: Dynamic Agent A (e.g., OSINT Researcher)
   ├── Node 2: Dynamic Agent B (e.g., Technical Writer)
   ├── Node 3: Dynamic Agent C (e.g., Strict QA Editor -> Conditional Loop)
   └── Node 4: Dynamic Agent D (e.g., Device Publisher -> ToolNode: .md/.docx/.pdf)
       |
       v (Unified OpenAI-Compatible SDK)
[Omnirouter / Multi-Provider Gateway (OpenRouter, LiteLLM, Anthropic, Gemini, Local Ollama)]
```

### 2.2. Spesifikasi Teknis Komponen
* **Frontend:** SvelteKit (Svelte 5 dengan Runes `$state`, `$derived`, `$effect`), TypeScript, TailwindCSS, `@xyflow/svelte` (Visual Graph Canvas), Lucide Icons. Package Manager: `pnpm`.
* **Backend:** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.0 (Async) + `asyncpg`, Alembic (Database Migration).
* **AI Orchestration:** `langgraph`, `langchain-core`, `langchain-openai` (sebagai klien universal ke Omnirouter).
* **Device & Document Engine:** `python-docx` (Word generator), `reportlab` / `weasyprint` (PDF generator), `mcp` (Model Context Protocol SDK), Browser File System Access API (`window.showDirectoryPicker`).
* **Database & Message Broker:** PostgreSQL 16 (penyimpanan skema agen, provider terenkripsi, histori eksekusi) & Redis 7 (Pub/Sub untuk *real-time streaming* SSE).

---

## 3. Sistem Desain UI/UX: "Retro Cyberpunk Blue" (Dark & Light Mode)

Antarmuka mengadopsi estetika **80s/90s Retro-Futuristic Cyberdeck & Mecha HUD** yang didominasi spektrum warna biru, sudut terpotong (*chamfered edges*), tipografi teknis/monospace, serta indikator layaknya terminal komando.

### 3.1. Palet Warna & Variabel Tema (Dual Theme Specification)

| Token CSS | Dark Mode ("Cyber-Abyss") | Light Mode ("Mecha-Lab Daylight") | Penggunaan |
| :--- | :--- | :--- | :--- |
| `--bg-primary` | `#040814` (Abyssal Midnight) | `#EBF3FA` (Cryo Ice Blue-White) | Latar belakang utama aplikasi |
| `--bg-surface` | `#0A1228` (Deep Cyber Navy) | `#FFFFFF` (Pure Lab White) | Panel kartu, modal, dan node agen |
| `--bg-elevated` | `#111E3E` (Sector Blue) | `#DCE8F5` (Steel Frost Blue) | Header tabel, input field, sidebar |
| `--text-primary` | `#E0F2FE` (Hologram Cyan-White) | `#071327` (Deep Naval Ink) | Teks utama dan judul |
| `--text-muted` | `#6488B8` (Muted Telemetry Blue) | `#416288` (Tactical Slate Blue) | Subtitle, label metadata, timestamp |
| `--accent-primary` | `#00F0FF` (Electric Neon Cyan) | `#0048E5` (High-Voltage Cobalt) | Tombol utama, border aktif, kursor |
| `--accent-secondary`| `#0066FF` (Hyper Cobalt Blue) | `#0088B8` (Cyber Cerulean) | Badge sekunder, garis penghubung node |
| `--status-success` | `#00FF9D` (Matrix Phosphor Mint) | `#008A5E` (Signal Emerald) | Status Approved / Tool Selesai |
| `--status-warning` | `#FFB800` (Amber CRT Warning) | `#D97706` (Industrial Amber) | Status Revisi / Loop Kembali |
| `--status-danger` | `#FF0055` (Cyber Crimson) | `#DC2626` (Alert Crimson) | Status Error / Rejected |
| `--border-glow` | `0 0 12px rgba(0, 240, 255, 0.35)` | `4px 4px 0px #0048E5` | Efek Glow (Dark) vs Hard Brutalist Shadow (Light) |

### 3.2. Karakteristik Visual & Komponen Khas Retro-Cyberpunk
1. **Chamfered Corners (Sudut Terpotong 45 Derajat):**
   Kartu Agent dan tombol utama tidak menggunakan `border-radius` melengkung biasa, melainkan poligon terpotong (`clip-path: polygon(0 0, calc(100% - 12px) 0, 100% 12px, 100% 100%, 12px 100%, 0 calc(100% - 12px))`).
2. **Tipografi:**
   * *Heading / HUD Labels:* `Orbitron` atau `Rajdhani` (Uppercase, `letter-spacing: 0.1em`).
   * *Body & Prompt Input:* `Space Grotesk` atau `Inter`.
   * *Terminal Logs, Token Counter & Code:* `JetBrains Mono` atau `Share Tech Mono`.
3. **Background Grid & CRT Scanlines:**
   * Latar belakang memiliki pola *blueprint grid* biru tipis (`background-size: 24px 24px`).
   * Opsi *toggle* efek **CRT Scanline Overlay** tipis (opasitas 3% pada Dark Mode) untuk memperkuat nuansa monitor retro.
4. **Theme Switcher ("OPTICAL MODE TOGGLE"):**
   * Terletak di Topbar HUD. Mengubah atribut `data-theme="dark"` atau `data-theme="light"` pada elemen `<html>`, disimpan secara persisten di `localStorage` dan disinkronkan melalui Svelte 5 Runes.

---

## 4. Spesifikasi Fitur & Modul Inti

### 4.1. Modul 1: Dynamic Provider & Omnirouter Vault
* Pengguna dapat mendaftarkan banyak penyedia LLM sekaligus (OpenRouter, LiteLLM, OpenAI, Anthropic, Google Gemini, Groq, hingga Local Ollama/vLLM).
* Menyimpan `base_url`, `api_key` (dienkripsi dengan AES/Fernet di database), dan `custom_headers`.
* Fitur **Auto-Fetch Models**: Menembak endpoint `/v1/models` milik Omnirouter untuk menarik daftar seluruh model yang tersedia secara otomatis beserta harga tokennya.

### 4.2. Modul 2: Dynamic Agent Studio (CRUD Jenis Agent Tanpa Batas)
Pengguna dapat membuat agen sebanyak apapun dengan atribut kustom:
* **Identitas CrewAI:** `name`, `role` (Peran), `goal` (Tujuan), `backstory` (Latar belakang keahlian).
* **Model & Parameter:** Memilih `provider_id` dan `model_name` spesifik per agen (misal: Agent 1 memakai model riset murah, Agent 2 memakai Claude 3.5 Sonnet, Agent 3 memakai model lokal), `temperature`, dan `max_tokens`.
* **Tipe Perilaku Node (`node_type`):**
  * `worker`: Mengeksekusi tugas, memproses data, atau menulis draf.
  * `reviewer`: Mengevaluasi hasil kerja `worker` sebelumnya dan mengeluarkan keputusan terstruktur (`is_approved: bool`, `feedback: str`).
  * `supervisor`: Mengatur delegasi dinamis ke beberapa agen di bawahnya.
* **Fitur Device & Hardware Capabilities (`tools_config`):** Daftar *checkbox* fitur perangkat yang boleh diakses oleh agen ini (lihat Modul 4).

### 4.3. Modul 3: Dynamic Workflow & LangGraph Compiler
* Pengguna merakit alur kerja (*pipeline*) dengan memilih agen mana saja yang terlibat (Agent 1 -> Agent 2 -> Agent 3 -> dst).
* Mendukung **Conditional Routing**: Jika sebuah node bertipe `reviewer` menghasilkan `is_approved = False`, alur otomatis melompat mundur ke node `worker` target beserta catatan `feedback` untuk diperbaiki.
* Dilengkapi pengaman `max_revisions` (default: 3 kali revisi) agar tidak terjadi *infinite loop* yang menguras saldo Omnirouter.

### 4.4. Modul 4: Local Device Bridge & Document Generator (Fitur Interaksi Perangkat)
Fitur ini memungkinkan agen AI "menyentuh" dan memproduksi artefak nyata di perangkat komputer pengguna melalui 4 kapabilitas modular:
1. **`tool_create_markdown` (`.md`):** Menghasilkan dokumentasi teknis, PRD, catatan Obsidian, atau kode ke dalam file Markdown.
2. **`tool_create_docx` (`.docx`):** Menghasilkan dokumen Microsoft Word terformat lengkap dengan Heading, Paragraf, Tabel, dan Bullet Points.
3. **`tool_create_pdf` (`.pdf`):** Merender laporan akhir menjadi dokumen PDF siap cetak.
4. **`tool_local_filesystem` (Read/List Local Folder):** Membaca daftar file atau isi file teks di dalam folder proyek pengguna sebagai bahan analisis agen.

**Mekanisme Sinkronisasi ke Perangkat Klien:**
* **Mode 1: Browser Direct Sync (Web File System Access API):** Di UI SvelteKit, pengguna menekan tombol `[MOUNT LOCAL DRIVE]` dan memilih folder di PC/Laptop mereka. Saat agen di backend memanggil tool pembuatan dokumen, FastAPI mengirimkan *stream* file melalui SSE (`event: device_write`), dan SvelteKit langsung menuliskan file tersebut ke *hard drive* lokal pengguna secara otomatis tanpa dialog *download* manual.
* **Mode 2: Local Workspace Mount (Docker/Self-Hosted):** FastAPI menulis langsung ke direktori host yang telah di-*mount* (`/workspace`) dengan pengaman *Path Traversal Protection*.
* **Human-in-the-Loop (HITL) Security Lock:** Opsi per agen `require_device_approval`. Jika aktif, sebelum file ditulis/ditimpa ke perangkat pengguna, muncul modal konfirmasi bergaya Cyberpunk HUD di layar SvelteKit (`[AUTHORIZE WRITE]` / `[ABORT]`).

### 4.5. Modul 5: Real-Time Telemetry & Execution Playground
* Menggunakan **Server-Sent Events (SSE)** untuk memancarkan status eksekusi secara *real-time*.
* Menampilkan *live thought process* tiap agen, indikator node mana yang sedang menyala di kanvas graf, *diff* atau alasan penolakan dari Reviewer, daftar file yang berhasil ditulis ke perangkat lokal, serta kalkulasi jumlah token dan estimasi biaya.

---

## 5. Skema Database Lengkap (PostgreSQL)

### 5.1. Tabel `llm_providers`
```sql
CREATE TABLE llm_providers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    provider_type VARCHAR(50) NOT NULL, -- 'openrouter', 'litellm', 'openai', 'ollama', 'custom'
    base_url VARCHAR(255) NOT NULL,
    api_key_encrypted TEXT NOT NULL,
    default_headers JSONB DEFAULT '{}'::jsonb,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 5.2. Tabel `agent_templates`
```sql
CREATE TABLE agent_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID NOT NULL REFERENCES llm_providers(id) ON DELETE RESTRICT,
    name VARCHAR(120) NOT NULL,
    avatar_code VARCHAR(50) DEFAULT 'cyber-bot-01',
    role VARCHAR(150) NOT NULL,
    goal TEXT NOT NULL,
    backstory TEXT NOT NULL,
    node_type VARCHAR(30) NOT NULL CHECK (node_type IN ('worker', 'reviewer', 'supervisor')),
    model_name VARCHAR(150) NOT NULL,
    temperature FLOAT DEFAULT 0.7,
    max_tokens INT DEFAULT 4096,
    tools_config JSONB DEFAULT '[]'::jsonb, -- Contoh: ["create_markdown", "create_docx", "read_local_files"]
    require_device_approval BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 5.3. Tabel `workflows`
```sql
CREATE TABLE workflows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(150) NOT NULL,
    description TEXT,
    max_revisions INT DEFAULT 3,
    graph_schema JSONB NOT NULL,
    -- Contoh struktur graph_schema:
    -- {
    --   "entry_point": "node_1",
    --   "nodes": [
    --     {"node_id": "node_1", "agent_id": "uuid-agent-1"},
    --     {"node_id": "node_2", "agent_id": "uuid-agent-2"},
    --     {"node_id": "node_3", "agent_id": "uuid-agent-3"}
    --   ],
    --   "edges": [
    --     {"from": "node_1", "to": "node_2", "type": "normal"},
    --     {"from": "node_2", "to": "node_3", "type": "normal"},
    --     {"from": "node_3", "type": "conditional", "on_approve": "END", "on_reject": "node_2"}
    --   ]
    -- }
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 5.4. Tabel `workflow_executions`
```sql
CREATE TABLE workflow_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    status VARCHAR(30) NOT NULL DEFAULT 'pending', -- 'pending', 'running', 'waiting_approval', 'completed', 'failed'
    task_prompt TEXT NOT NULL,
    final_output TEXT,
    generated_files JSONB DEFAULT '[]'::jsonb, -- Daftar file yang dibuat oleh agent
    execution_logs JSONB DEFAULT '[]'::jsonb,
    total_tokens INT DEFAULT 0,
    estimated_cost_usd NUMERIC(10, 6) DEFAULT 0,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);
```

---

## 6. Blueprint Inti Backend (FastAPI + Dynamic LangGraph + Device Tools)

### 6.1. Struktur Direktori Backend
```text
backend/
├── app/
│   ├── main.py                  # Entrypoint FastAPI & CORS
│   ├── core/
│   │   ├── config.py            # Pydantic Settings (.env)
│   │   ├── database.py          # Async SQLAlchemy Session
│   │   └── security.py          # Fernet API Key Encryption & Path Sanitizer
│   ├── models/                  # SQLAlchemy ORM Models
│   ├── schemas/                 # Pydantic v2 Request/Response Schemas
│   ├── engine/
│   │   ├── state.py             # DynamicTeamState TypedDict
│   │   ├── llm_factory.py       # Omnirouter / Multi-Provider Client Builder
│   │   ├── tool_registry.py     # Device & Document Tools (.md, .docx, .pdf)
│   │   └── compiler.py          # Dynamic LangGraph StateGraph Compiler
│   └── api/
│       └── v1/
│           ├── providers.py
│           ├── agents.py
│           ├── workflows.py
│           └── executions.py    # Trigger & SSE Stream Endpoint
├── workspace/                   # Sandbox folder untuk operasi file lokal
├── alembic/
├── pyproject.toml
└── Dockerfile
```

### 6.2. Spesifikasi State & Dynamic Compiler (`backend/app/engine/compiler.py`)
```python
from typing import TypedDict, Annotated, List, Dict, Any
import operator
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

class ReviewDecision(BaseModel):
    is_approved: bool = Field(description="True jika draf memenuhi standar kualitas, False jika butuh revisi")
    feedback: str = Field(description="Instruksi perbaikan spesifik jika ditolak, atau ringkasan jika disetujui")

class DynamicTeamState(TypedDict):
    task_prompt: str
    shared_context: str
    current_draft: str
    reviewer_feedback: str
    is_approved: bool
    revision_count: int
    generated_files: Annotated[List[Dict[str, str]], operator.add]
```

---

## 7. Spesifikasi Endpoint REST API & SSE

| Method | Endpoint | Deskripsi |
| :--- | :--- | :--- |
| `POST` | `/api/v1/providers` | Menambahkan provider baru (OpenRouter, LiteLLM, Ollama, dll) |
| `GET` | `/api/v1/providers` | Mengambil daftar semua provider terdaftar |
| `GET` | `/api/v1/providers/{id}/models` | Menarik daftar model dari endpoint `/models` provider terkait |
| `POST` | `/api/v1/agents` | Membuat template Agent baru beserta konfigurasi *tools* perangkat |
| `GET` | `/api/v1/agents` | Mengambil semua daftar Agent yang tersedia |
| `PUT` | `/api/v1/agents/{id}` | Memperbarui persona, model, atau *tools* Agent |
| `DELETE`| `/api/v1/agents/{id}` | Menghapus template Agent |
| `GET` | `/api/v1/tools` | Mengambil daftar fitur interaksi perangkat yang bisa dipasang ke Agent |
| `POST` | `/api/v1/workflows` | Menyimpan skema graf Multi-Agent (nodes & conditional edges) |
| `POST` | `/api/v1/workflows/{id}/execute`| Memulai eksekusi asinkron Multi-Agent |
| `GET` | `/api/v1/executions/{id}/stream`| Stream SSE untuk log pergerakan agen & pengiriman file ke perangkat lokal |
| `POST` | `/api/v1/executions/{id}/approve-tool` | Endpoint konfirmasi HITL untuk mengizinkan penulisan file ke perangkat |

---

## 8. Arsitektur Frontend SvelteKit & Struktur Halaman

### 8.1. Struktur Direktori Frontend (`frontend/`)
```text
frontend/
├── src/
│   ├── app.css                        # Definisi CSS Variables Retro Cyberpunk Blue (Dark & Light)
│   ├── lib/
│   │   ├── stores/
│   │   │   ├── theme.svelte.ts        # Svelte 5 Rune Store untuk Dark/Light Theme & CRT Toggle
│   │   │   └── deviceBridge.svelte.ts # Web File System Access API Handler (Local Folder Mount)
│   │   ├── components/
│   │   │   ├── ui/
│   │   │   │   ├── CyberButton.svelte # Tombol bersudut potong (chamfered) dengan efek neon/shadow
│   │   │   │   ├── CyberCard.svelte   # Panel HUD dengan aksen sudut biru
│   │   │   │   ├── ThemeToggle.svelte # Switcher Cyber-Abyss (Dark) <-> Mecha-Lab (Light)
│   │   │   │   └── TerminalLog.svelte # Layar monitor log eksekusi real-time
│   │   │   └── workflow/
│   │   │       └── AgentNode.svelte   # Custom Node untuk kanvas Xyflow
│   └── routes/
│       ├── +layout.svelte             # Shell HUD, Sidebar Navigasi, Topbar Status & Theme Switcher
│       ├── +page.svelte               # Dashboard Telemetry & Quick Launch
│       ├── providers/+page.svelte     # Omnirouter & LLM Provider Vault
│       ├── agents/+page.svelte        # Dynamic Agent Studio (CRUD & Hardware Tool Selector)
│       ├── workflows/+page.svelte     # Visual Multi-Agent Graph Builder
│       └── playground/+page.svelte    # Live Execution Console + Local Drive Mount Control
├── package.json
├── tailwind.config.ts
└── svelte.config.js
```
