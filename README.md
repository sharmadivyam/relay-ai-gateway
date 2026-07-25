# AI Gateway

![tests](https://github.com/<you>/<repo>/actions/workflows/tests.yml/badge.svg)

A production-grade **AI Gateway / Reverse Proxy** with a built-in **React analytics dashboard**. Sits between client applications and LLM providers, adding auth, rate limiting, prompt guardrails, semantic caching, smart routing, prompt compression, savings telemetry, document ingestion, and a live web UI — all behind feature flags.

---

## Features

| Feature | Status | Flag |
|---|---|---|
| JWT + API-key authentication | Always on | — |
| Per-tier rate limiting (Redis / in-memory) | Always on | — |
| Input guardrails — 26+ prompt-injection patterns | Always on | — |
| Semantic cache (ChromaDB, cosine ≥ 0.95, 24 h TTL) | Always on | — |
| Output guardrails — 8 PII redaction rules | Always on | — |
| Async telemetry + cost logging | Always on | — |
| **Read-only analytics API** — 3 GET endpoints | Always on | — |
| **Smart routing** — cheap vs. premium model | Off by default | `ENABLE_SMART_ROUTING` |
| **Prompt compression** — LLMLingua-2 | Off by default | `ENABLE_PROMPT_COMPRESSION` |
| **Document ingestion** — PDF / DOCX / PPTX → Markdown | Always on | — |
| **React dashboard** ("Relay") — live metrics, request feed, charts | Always on (needs Node) | — |
| **Evals page** — live in-app eval runner + "try your own case" sandbox | Always on | — |
| **Regression eval suite** — 61 golden cases, pure-function checks | Always on | — |
| **GitHub Actions CI** — full test suite on every push/PR | Always on | — |

---

## Quick Start

> Moving this project from the Windows work laptop to a personal Mac? Follow [`SETUP_ON_MAC.md`](SETUP_ON_MAC.md) — it covers zipping (with the right exclusions) and reproducing the current running system on macOS.

### 1. Clone and create the virtual environment

```powershell
git clone <repo-url>
cd my_proj
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install Python dependencies

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 3. Configure environment

```powershell
copy .env.example .env
# Open .env and fill in OPENAI_API_KEY (and OPENAI_BASE_URL if using Cerebras or another provider)
```

Minimum viable `.env`:

```env
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.cerebras.ai/v1   # or https://api.openai.com/v1
JWT_SECRET_KEY=change-me-to-a-long-random-string
DATABASE_URL=sqlite+aiosqlite:///./gateway_dev.db
```

### 4. Start the gateway

```powershell
.\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8001
```

Swagger UI: **http://127.0.0.1:8001/docs**

### 5. Start the dashboard (dev mode)

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Dashboard: **http://localhost:5173** — register an account and log in.

> In dev the Vite server proxies `/v1` and `/auth` to `http://127.0.0.1:8001` automatically — no CORS configuration needed.

---

## Production Deployment (single process)

Build the frontend once, then let FastAPI serve it:

```powershell
cd frontend
npm run build     # outputs frontend/dist/

cd ..
.\.venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8001
```

`main.py` auto-detects `frontend/dist/` and mounts it at `/` after all API routes.  
Everything — API + dashboard — runs from **one process on one port**.

---

## Demo Seed

Populates the dashboard with believable data before a screen recording:

```powershell
.\.venv\Scripts\python.exe demo_seed.py --email demo@gateway.ai --password demo1234
```

Fires 11 scripted requests — simple, complex, cached duplicate, and one guardrail-blocked — so every column in the live feed is exercised immediately.

---

## Endpoints

### Health

```
GET /health
```
Returns `{"status": "ok"}`. No auth required. Liveness probe.

---

### Auth

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/register` | None | Create a user account |
| POST | `/auth/login` | None | Get a JWT access token |
| POST | `/auth/keys` | JWT | Create an API key (raw key shown once) |
| GET | `/auth/keys` | JWT | List active API keys |

```powershell
# Register
curl -X POST http://localhost:8001/auth/register `
  -H "Content-Type: application/json" `
  -d '{"email": "you@example.com", "password": "secret"}'

# Login → get JWT
curl -X POST http://localhost:8001/auth/login `
  -H "Content-Type: application/json" `
  -d '{"email": "you@example.com", "password": "secret"}'
# → {"access_token": "eyJ...", "token_type": "bearer"}
```

---

### Chat Completions (OpenAI-compatible)

```
POST /v1/chat/completions
Authorization: Bearer <jwt-or-api-key>
```

Drop-in replacement for the OpenAI chat completions endpoint.

```powershell
curl -X POST http://localhost:8001/v1/chat/completions `
  -H "Authorization: Bearer eyJ..." `
  -H "Content-Type: application/json" `
  -d '{"model": "gpt-oss-120b", "messages": [{"role": "user", "content": "Hello!"}]}'
```

**Response extras** (beyond standard OpenAI fields):

```json
{
  "gateway_cached": false,
  "gateway_fallback": false
}
```

---

### Document Ingestion

```
POST /v1/documents/ingest
Authorization: Bearer <jwt-or-api-key>
Content-Type: multipart/form-data
```

Upload a file and receive its contents as Markdown. Supported: **PDF, DOCX, PPTX**, HTML, CSV, JSON, XML, and more.

```powershell
curl -X POST http://localhost:8001/v1/documents/ingest `
  -H "Authorization: Bearer eyJ..." `
  -F "file=@report.pdf"
# → {"markdown": "...", "original_bytes": 204800, "filename": "report.pdf"}
```

---

### Analytics (read-only, per-user)

All three endpoints filter to the logged-in user's own data. No writes.

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/v1/analytics/overview` | JWT / API Key | Aggregate totals |
| GET | `/v1/analytics/requests?limit=50` | JWT / API Key | Most-recent request log, newest first |
| GET | `/v1/analytics/savings-timeseries?days=7` | JWT / API Key | Per-day savings breakdown |

**`/v1/analytics/overview` response:**

```json
{
  "total_requests": 142,
  "total_savings_usd": 0.0312,
  "cache_hit_rate": 0.18,
  "avg_latency_ms": 831.4,
  "total_tokens": 58300
}
```

**`/v1/analytics/savings-timeseries` response:**

```json
[
  { "date": "2026-07-21", "compression_savings_usd": 0.0014, "routing_savings_usd": 0.0031 },
  { "date": "2026-07-22", "compression_savings_usd": 0.0009, "routing_savings_usd": 0.0018 }
]
```

---

### Evals (live demo — no LLM, no quota)

Powers the dashboard **Evals** page. Runs a curated subset of the golden dataset
and arbitrary user text through the real `route()` / `scan_input()` / `scan_output()`
functions. These are pure, deterministic local functions — no LLM calls, no API
credits, no rate-limit risk.

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/v1/evals/cases` | JWT / API Key | Curated demo cases (3 per type) in display order |
| POST | `/v1/evals/run-case` | JWT / API Key | Run one curated case by `id`; returns pass/fail + full detail |
| POST | `/v1/evals/sandbox` | JWT / API Key | Run arbitrary text through a chosen mode (live "prove it") |

**`POST /v1/evals/run-case`** body `{ "id": "out_ssn_001" }` → returns the exact
input, `expected → actual`, chosen model (routing), before/after redacted output,
matched reason, `redacted_types`, and `duration_ms`.

**`POST /v1/evals/sandbox`** body `{ "mode": "guardrail_output", "text": "SSN 123-45-6789" }`
(`mode` ∈ `routing` | `guardrail_input` | `guardrail_output`, max 5000 chars):

```json
{
  "mode": "guardrail_output",
  "input": "SSN 123-45-6789",
  "action": "redacted",
  "model": null,
  "reason": "Redacted: SSN(x1)",
  "output": "SSN [SSN REDACTED]",
  "redacted_types": ["SSN"],
  "duration_ms": 0.03
}
```

---

## Dashboard Screens

The dashboard is branded **"Relay"** and uses a light editorial theme (Space Grotesk / Space Mono).

| Screen | Route | Data source |
|---|---|---|
| **Overview** | `/` | `GET /v1/analytics/overview` + `GET /v1/analytics/requests` — polled every 3 s |
| **Intelligence** (Routing & Savings) | `/routing` | `GET /v1/analytics/savings-timeseries` — stacked bar chart (Recharts) |
| **Guardrails** | `/guardrails` | `GET /v1/analytics/guardrails-timeseries` + guardrail events feed |
| **Evals** | `/evals` | `GET /v1/evals/cases` + `POST /v1/evals/run-case` + `POST /v1/evals/sandbox` |
| **Chat** | `/chat` | `POST /v1/chat/completions` — interactive chat playground |
| **Documents** | `/documents` | `POST /v1/documents/ingest` — drag-and-drop upload + Markdown preview |
| **API Keys** | `/keys` | `GET`/`POST /auth/keys` — create & list keys (raw key shown once) |

New rows in the request feed flash briefly on arrival. Badges use the green accent for `simple`/`cached`/`passed`, amber for `complex`/`redacted`, red for `blocked`.

### Evals page (built for live demos)

- **Run evals** ticks through 9 curated cases (3 routing, 3 input-guardrail, 3 output-guardrail) one-by-one with a live pass counter and progress bar — all green.
- **View proof** on any case reveals the exact input, before → after redaction (with each `[… REDACTED]` token highlighted), the decision reason (including the literal regex that matched), the chosen model, and the raw API JSON response.
- **Try your own case** (collapsible) is a live sandbox: pick a mode, type anything, and run it through the same real function. Arbitrary input → real output is the proof that nothing is hardcoded. Runs entirely on pure functions, so it never touches the LLM or free-tier quota.

---

## Configuration

All settings are loaded from `.env` via Pydantic `BaseSettings`. Restart the server after changes.

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | _(required)_ | Provider API key |
| `OPENAI_BASE_URL` | `https://api.cerebras.ai/v1` | Any OpenAI-compatible endpoint |
| `JWT_SECRET_KEY` | `change-me` | HS256 signing key — **change this in production** |
| `JWT_EXPIRE_MINUTES` | `60` | JWT lifetime |
| `DATABASE_URL` | `sqlite+aiosqlite:///./gateway_dev.db` | SQLite (dev) or `postgresql+asyncpg://...` (prod) |
| `REDIS_URL` | `redis://localhost:6379` | Rate limiter backend — auto-falls back to in-memory |
| `PRIMARY_MODEL` | `gpt-oss-120b` | Model used by default |
| `FALLBACK_MODEL` | `llama3.1-8b` | Used automatically on 429 / 503 |
| `CACHE_SIMILARITY_THRESHOLD` | `0.95` | Cosine similarity cutoff for cache hits |
| `CACHE_TTL_HOURS` | `24` | How long cache entries live |
| `RATE_LIMIT_FREE` | `10000` | Tokens per minute — free tier |
| `RATE_LIMIT_PRO` | `100000` | Tokens per minute — pro tier |
| `RATE_LIMIT_ENTERPRISE` | `1000000` | Tokens per minute — enterprise tier |
| `ENABLE_SMART_ROUTING` | `false` | Route simple prompts to a cheaper model |
| `CHEAP_MODEL` | `gpt-4o-mini` | Model for simple prompts |
| `PREMIUM_MODEL` | `gpt-4o` | Model for complex prompts |
| `ENABLE_PROMPT_COMPRESSION` | `false` | Compress long prompts with LLMLingua-2 |
| `COMPRESSION_THRESHOLD_TOKENS` | `1500` | Prompts shorter than this are never compressed |

---

## Feature Flags

All new behaviour is **off by default**. The existing request flow is byte-for-byte unchanged unless a flag is explicitly enabled.

### Smart Routing

```env
ENABLE_SMART_ROUTING=true
```

Classifies prompts as **simple** or **complex** (token count, code markers, keywords). Routes simple prompts to `CHEAP_MODEL`, complex ones to `PREMIUM_MODEL`. Per-request routing savings (premium cost − actual cost) are recorded in `request_logs` and rendered in the **Routing & Savings** dashboard screen.

### Prompt Compression

```env
ENABLE_PROMPT_COMPRESSION=true
COMPRESSION_THRESHOLD_TOKENS=1500
```

Compresses prompts above the threshold with LLMLingua-2 at 50 % reduction before sending to the LLM. Compression savings in USD are recorded in `request_logs` and shown in the savings chart.

---

## Running Tests

```powershell
.\.venv\Scripts\pytest.exe app/tests/ -v
```

Expected: **149 tests, 0 failures**.

| Test file | What it covers |
|---|---|
| `test_auth.py` | Registration, login, API key CRUD, health check (4 tests) |
| `test_guardrails.py` | 48 red-team prompts — all attack categories + clean pass-throughs |
| `test_smart_router.py` | 13 unit tests — simple / complex routing classification |
| `test_prompt_compressor.py` | 10 unit tests — threshold logic (compressor mocked, no model download) |
| `test_analytics.py` | 13 tests — overview aggregation, request list, timeseries, per-user scoping, auth |
| `test_regression_eval.py` | 61 parametrized cases from `eval_dataset.json` — routing + guardrails golden dataset |

Run only the regression eval suite (fast, no server, no LLM):

```powershell
.\.venv\Scripts\pytest.exe app/tests/test_regression_eval.py -v
```

### CI (GitHub Actions)

On every push to `main` and every pull request, `.github/workflows/tests.yml` runs the full suite on **Python 3.12** (Ubuntu) using `requirements-ci.txt` — a lean dependency set that omits `llmlingua`, `markitdown`, and `chromadb` because those packages are lazily imported and never triggered by the test suite.

No API keys or secrets are required in CI — the eval suite calls `route()`, `scan_input()`, and `scan_output()` directly.

Replace `<you>/<repo>` in the badge URL at the top of this file with your GitHub org/repo once pushed.

---

## Benchmark

Analytically estimates routing cost savings across 32 synthetic prompts (no server or API credits needed):

```powershell
.\.venv\Scripts\python.exe benchmark/run_benchmark.py
```

Results written to `benchmark/results.md`.

---

## Project Structure

```
my_proj/
├── app/
│   ├── main.py                   FastAPI app factory + lifespan + static file mount
│   ├── config.py                 Settings (Pydantic BaseSettings)
│   ├── middleware/
│   │   ├── auth.py               JWT + API-key verification, AuthenticatedCaller
│   │   └── rate_limiter.py       Redis TPM limiter + in-memory fallback
│   ├── routers/
│   │   ├── auth.py               /auth/* endpoints
│   │   ├── proxy.py              /v1/chat/completions — 7-step pipeline
│   │   ├── documents.py          /v1/documents/ingest
│   │   ├── analytics.py          /v1/analytics/* — 3 read-only GET endpoints
│   │   └── evals.py              /v1/evals/* — cases, run-case, sandbox (pure fns)
│   ├── services/
│   │   ├── llm_router.py         LLM provider adapter + cost table
│   │   ├── telemetry.py          Async savings logger (BackgroundTasks)
│   │   ├── cache.py              Semantic cache (ChromaDB + ONNX)
│   │   ├── guardrails_in.py      Input guardrails (26+ regex patterns)
│   │   ├── guardrails_out.py     Output PII redaction (8 rules)
│   │   ├── smart_router.py       Prompt complexity classifier (pure function)
│   │   ├── prompt_compressor.py  LLMLingua-2 wrapper (lazy singleton)
│   │   └── document_ingestion.py MarkItDown wrapper (lazy singleton)
│   ├── db/
│   │   ├── models.py             SQLAlchemy ORM: User, ApiKey, RequestLog
│   │   ├── schemas.py            Pydantic request/response/telemetry shapes
│   │   └── session.py            Async DB session (SQLite/PostgreSQL)
│   └── tests/
│       ├── conftest.py           In-memory SQLite fixture
│       ├── eval_dataset.json     Golden dataset — 61 routing + guardrail cases
│       ├── test_auth.py
│       ├── test_guardrails.py
│       ├── test_smart_router.py
│       ├── test_prompt_compressor.py
│       ├── test_analytics.py
│       └── test_regression_eval.py  Parametrized eval runner (loads eval_dataset.json)
│
├── .github/
│   └── workflows/
│       └── tests.yml             CI — pytest on push/PR (Python 3.12, requirements-ci.txt)
│
├── frontend/                     React 18 + Vite + TypeScript + Tailwind
│   ├── package.json
│   ├── vite.config.ts            Dev proxy: /v1 + /auth → http://127.0.0.1:8001
│   ├── index.html
│   ├── tailwind.config.js
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx               Router + ProtectedLayout
│   │   ├── index.css
│   │   ├── api/client.ts         Fetch wrapper — JWT in memory, not localStorage
│   │   ├── context/AuthContext.tsx
│   │   ├── components/
│   │   │   ├── Nav.tsx           Top nav bar ("Relay" brand + all screen links)
│   │   │   ├── MetricCard.tsx
│   │   │   ├── Badge.tsx         routing / guardrail / cached badges
│   │   │   └── Skeleton.tsx      Loading skeletons
│   │   └── pages/
│   │       ├── Login.tsx         Email + password + register toggle
│   │       ├── Overview.tsx      Metric cards + live request table (3 s poll)
│   │       ├── Routing.tsx       Savings chart (Recharts) + day-range selector
│   │       ├── Guardrails.tsx    Guardrail activity chart + events feed
│   │       ├── Evals.tsx         Live eval runner + proof expanders + sandbox
│   │       ├── Chat.tsx          Interactive chat playground
│   │       ├── Documents.tsx     Drag-and-drop upload + Markdown preview
│   │       └── Keys.tsx          API key create/list management
│   └── dist/                     Built output (git-ignored; auto-served by FastAPI)
│
├── demo_seed.py                  Fires 11 realistic requests before a demo recording
├── benchmark/
│   ├── prompts.json
│   ├── run_benchmark.py
│   └── results.md
├── superset/
│   └── dashboard_queries.sql     5 pre-built Superset analytics queries
├── docker-compose.yml            PostgreSQL + Redis + ChromaDB + Superset
├── requirements.txt              Full local install (includes llmlingua, markitdown, chromadb)
├── requirements-ci.txt           Lean CI deps — omits heavy lazy-import packages
├── pytest.ini
├── .env.example
├── ARCHITECTURE.md               Full design reference
├── MIGRATION_GUIDE.md            Work laptop → personal laptop (production upgrade)
├── SETUP_ON_MAC.md               Zip on Windows → run current system on Mac
└── PROGRESS.md                   Build log
```

---

## Dev vs. Production

| Component | Dev (no Docker) | Production (Docker) |
|---|---|---|
| Database | SQLite (`gateway_dev.db`) | PostgreSQL 16 |
| Rate limiter | In-memory dict | Redis 7 |
| Vector cache | ChromaDB `PersistentClient` (`./chromadb_data`) | ChromaDB Docker container |
| LLM SDK | `openai` SDK + custom `base_url` | `litellm` (see `MIGRATION_GUIDE.md`) |
| Frontend | Vite dev server (port 5173) | Built into `frontend/dist/`, served by FastAPI |

```powershell
# Full production stack
docker compose up -d
```

---

## Security

- Passwords hashed with **bcrypt** (work factor 12); 72-byte truncation is explicit.
- API keys: only the **SHA-256 hash** is stored — raw key shown once and never persisted.
- JWT signed with **HS256**; expires after 60 minutes (configurable).
- Dashboard JWT stored **in React state / memory only** — never written to `localStorage`.
- Input guardrails cover [OWASP LLM Top 10](https://owasp.org/www-project-top-10-for-large-language-model-applications/) categories LLM01, LLM02, and LLM06.
- Output guardrails redact SSN, credit card, email, phone, API keys, bearer tokens, IPs, and passwords.

---

## Architecture

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full design reference, including the 7-step request lifecycle, all component deep-dives, data model schemas, dashboard architecture, and every design decision and trade-off.
