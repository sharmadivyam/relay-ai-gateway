# AI Gateway — Build Progress Log

## Project
Real-Time AI Gateway & Observability Engine  
A production-grade reverse proxy between client apps and LLMs with semantic caching, guardrails, smart routing, prompt compression, savings telemetry, document ingestion, and a built-in React analytics dashboard.

---

## Environment

| Item | Detail |
|---|---|
| OS | Windows 11 (PowerShell) |
| Python | 3.14.5 via `py` launcher (NOT `python` — alias disabled) |
| Node.js | Required for frontend — `node --version` to verify |
| Venv | `.venv\Scripts\python.exe` / `.venv\Scripts\uvicorn.exe` |
| Pip flags | Use `--trusted-host pypi.org --trusted-host files.pythonhosted.org` on this machine (corporate SSL) |
| Docker | NOT YET INSTALLED — needs Docker Desktop |
| Backend port | `8001` (Vite dev proxy points here) |

### Key gotchas

- Use `py` not `python` on this machine
- Use `.\.venv\Scripts\<tool>.exe` not bare commands
- `litellm` CANNOT be installed — requires Rust/maturin; rustup download fails on corporate SSL. **Replaced with `openai` SDK.**
- Unicode chars (✓ ⚠) crash on Windows cp1252 terminal — use ASCII `[OK]` / `[WARN]`
- PowerShell uses `;` not `&&` to chain commands

---

## Phase Roadmap

### Gateway Backend

| Phase | Status | Focus |
|---|---|---|
| **Phase 1** | ✅ COMPLETE | Core router, auth, DB models, rate limiter |
| **Phase 2** | ✅ COMPLETE | Async telemetry + savings logging |
| **Phase 3** | ✅ COMPLETE | ChromaDB semantic cache (ONNX embeddings) |
| **Phase 4** | ✅ COMPLETE | Guardrails engine — 26+ input patterns, 8 PII redaction rules, 48 red-team tests |
| **Phase 5** | ✅ COMPLETE | Smart routing — cheap vs. premium model, per-request routing savings |
| **Phase 6** | ✅ COMPLETE | Prompt compression — LLMLingua-2, lazy singleton, threshold-gated |
| **Phase 7** | ✅ COMPLETE | Document ingestion — PDF/DOCX/PPTX → Markdown (MarkItDown) |

### Dashboard UI

| Phase | Status | Focus |
|---|---|---|
| **Dashboard Phase 0** | ✅ COMPLETE | Read-only analytics API (`/v1/analytics/*`) — 3 GET endpoints, 13 tests |
| **Dashboard Phase 1** | ✅ COMPLETE | Frontend scaffold — React 18 + Vite + TypeScript + Tailwind |
| **Dashboard Phase 2** | ✅ COMPLETE | Auth screen — login + register, JWT stored in React context (not localStorage) |
| **Dashboard Phase 3** | ✅ COMPLETE | Overview screen — 4 metric cards + live request table, 3 s polling, new-row flash |
| **Dashboard Phase 4** | ✅ COMPLETE | Routing & Savings screen — stacked bar chart (Recharts), day-range selector |
| **Dashboard Phase 5** | ✅ COMPLETE | Documents screen — drag-and-drop upload, Markdown preview |
| **Dashboard Phase 6** | ✅ COMPLETE | Polish — top nav bar, loading skeletons, `demo_seed.py` script |

### Regression Eval Suite + CI

| Phase | Status | Focus |
|---|---|---|
| **Eval Phase 0** | ✅ COMPLETE | Golden dataset — `eval_dataset.json` (61 entries: 13 routing, 30 input guardrail, 18 output guardrail) |
| **Eval Phase 1** | ✅ COMPLETE | Eval runner — `test_regression_eval.py` (parametrized, calls pure functions directly) |
| **Eval Phase 2** | ✅ COMPLETE | CI — `.github/workflows/tests.yml` + `requirements-ci.txt` (Python 3.12, no secrets) |

**Test suite: 149 tests, 0 failures** (as of 2026-07-23)

### In-App Evals Demo Page

| Phase | Status | Focus |
|---|---|---|
| **Evals UI Phase 0** | ✅ COMPLETE | Backend `app/routers/evals.py` — `GET /cases`, `POST /run-case` over curated 9-case subset (pure fns, no LLM/quota) |
| **Evals UI Phase 1** | ✅ COMPLETE | `frontend/src/pages/Evals.tsx` — live animated runner (sequential reveal, pass counter, progress bar), light editorial theme |
| **Evals UI Phase 2** | ✅ COMPLETE | Proof enhancements — per-case "View proof" (input, before/after redaction, matched regex/reason, raw JSON) + enriched `EvalResult` (input/output/model) |
| **Evals UI Phase 3** | ✅ COMPLETE | `POST /v1/evals/sandbox` + collapsible "Try your own case" — arbitrary text through real functions (anti-hardcode proof) |

All 9 curated demo cases pass; `tsc --noEmit` + `vite build` clean. Runs with zero LLM/API-key usage.

---

## Run Commands

```powershell
# ── Backend ──────────────────────────────────────────────────────────────────

# Activate venv
.\.venv\Scripts\Activate.ps1

# Install Python deps
.\.venv\Scripts\python.exe -m pip install -r requirements.txt `
  --trusted-host pypi.org --trusted-host files.pythonhosted.org

# Start gateway (port 8001 — matches Vite proxy config)
.\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8001

# Run full test suite
.\.venv\Scripts\pytest.exe app/tests/ -v

# Run regression eval suite only (61 cases, <1 s, no server/LLM)
.\.venv\Scripts\pytest.exe app/tests/test_regression_eval.py -v

# ── Frontend (dev mode — two terminals) ──────────────────────────────────────

cd frontend
npm install
npm run dev        # → http://localhost:5173

# ── Frontend (production build) ──────────────────────────────────────────────

cd frontend
npm run build      # outputs frontend/dist/
cd ..
# FastAPI auto-detects dist/ and serves it at / (after all API routes)
.\.venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8001

# ── Demo seed (populate dashboard before recording) ──────────────────────────

.\.venv\Scripts\python.exe demo_seed.py --email demo@gateway.ai --password demo1234

# ── Infrastructure (after Docker installed) ───────────────────────────────────

docker compose up -d postgres redis chromadb
```

---

## Dashboard Architecture Summary

```
frontend/src/
├── api/client.ts           JWT kept in module-level var (not localStorage)
├── context/AuthContext.tsx React Context synced to client.ts on login/logout
├── App.tsx                 BrowserRouter + ProtectedLayout
├── components/             MetricCard · Badge · Skeleton · Nav
└── pages/
    ├── Login.tsx           Email/password + register toggle; auto-login
    ├── Overview.tsx        4 metric cards + request table (3 s poll; new rows flash)
    ├── Routing.tsx         Stacked bar chart; compression + routing savings; 7/14/30d
    └── Documents.tsx       Drag-and-drop + file-picker; POST multipart; Markdown preview
```

**Deployment:** `npm run build` → `frontend/dist/` → FastAPI mounts it **after** all API routers.  
Single process, single port, no CORS.

---

## All Files Created / Modified

### Backend additions (Dashboard Phase 0)
- `app/routers/analytics.py` — new file (read-only, 3 GET endpoints)
- `app/tests/test_analytics.py` — new file (13 tests)
- `app/main.py` — additive: analytics router registered + static file mount

### Frontend (Dashboard Phases 1–6)
- `frontend/package.json`
- `frontend/vite.config.ts`
- `frontend/index.html`
- `frontend/tailwind.config.js`
- `frontend/postcss.config.js`
- `frontend/tsconfig.json` / `tsconfig.app.json` / `tsconfig.node.json`
- `frontend/src/main.tsx`
- `frontend/src/App.tsx`
- `frontend/src/index.css`
- `frontend/src/api/client.ts`
- `frontend/src/context/AuthContext.tsx`
- `frontend/src/components/Nav.tsx`
- `frontend/src/components/MetricCard.tsx`
- `frontend/src/components/Badge.tsx`
- `frontend/src/components/Skeleton.tsx`
- `frontend/src/pages/Login.tsx`
- `frontend/src/pages/Overview.tsx`
- `frontend/src/pages/Routing.tsx`
- `frontend/src/pages/Documents.tsx`

### Support scripts
- `demo_seed.py` — new file (seeds 11 realistic requests before demo recording)

### Regression eval suite + CI (Eval Phases 0–2)
- `app/tests/eval_dataset.json` — golden dataset (61 entries consolidated from existing guardrail/router tests)
- `app/tests/test_regression_eval.py` — parametrized eval runner (3 test functions, 61 cases)
- `.github/workflows/tests.yml` — GitHub Actions workflow (push to main + PRs)
- `requirements-ci.txt` — lean CI deps (excludes llmlingua, markitdown, chromadb)

### In-app Evals demo page + sandbox (Evals UI Phases 0–3)
- `app/routers/evals.py` — new file: `/v1/evals/cases`, `/v1/evals/run-case`, `/v1/evals/sandbox` (curated subset of `eval_dataset.json`; pure functions, no LLM)
- `app/main.py` — additive: `evals` router registered
- `frontend/src/pages/Evals.tsx` — new page: live runner, per-case proof expanders, "Try your own case" sandbox
- `frontend/src/api/client.ts` — added `EvalCase`/`EvalResult`/`SandboxResult` types + `evalCases()`/`runEvalCase()`/`runSandbox()`
- `frontend/src/App.tsx` — added `/evals` route
- `frontend/src/components/Nav.tsx` — added Evals nav link
- `frontend/src/index.css` — added `result-pop` reveal keyframe

### Docs updated
- `README.md` — full rewrite covering all features, dashboard, deployment, 149-test suite, CI badge; Evals page + `/v1/evals/*` endpoints
- `ARCHITECTURE.md` — v3.2: section 4.13 Evals demo API & sandbox, updated directory tree + API reference
- `PROGRESS.md` — this file
- `MIGRATION_GUIDE.md` — added Node.js + frontend migration notes, CI section, Evals router note
- `SETUP_ON_MAC.md` — new file: zip on Windows (with exclusions) → reproduce current running system on Mac

---

## LLM Provider Notes

| Provider | Model string in .env | How it connects |
|---|---|---|
| Cerebras | `gpt-oss-120b` | openai SDK with custom `base_url` |
| Fallback | `llama3.1-8b` | Same — auto-triggered on 429/503 |
| OpenAI (personal laptop) | `gpt-4o-mini` / `gpt-4o` | via litellm after migration |

---

## Tested-On Reference

| Milestone | Date | Python | Node | OS | Notes |
|---|---|---|---|---|---|
| Gateway scaffold + server | 2026-07-19 | 3.14.5 | — | Windows 11 PowerShell | openai SDK, no Docker |
| Full backend (all 75 tests) | 2026-07-19 | 3.14.5 | — | Windows 11 PowerShell | LLMProvider adapter added |
| Dashboard UI (88 tests) | 2026-07-23 | 3.14.5 | 22.x | Windows 11 PowerShell | Vite build passes; 0 TS errors |
| Regression eval + CI (149 tests) | 2026-07-23 | 3.14.5 | 22.x | Windows 11 PowerShell | 61 golden cases; CI uses Python 3.12 + requirements-ci.txt |
| In-app Evals page + sandbox | 2026-07-24 | 3.14.5 | 22.x | Windows 11 PowerShell | 9/9 curated cases pass; tsc + vite build clean; zero LLM/quota usage |
