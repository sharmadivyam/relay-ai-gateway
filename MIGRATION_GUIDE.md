# Migration Guide — Work Laptop → Personal Laptop

This file is the single source of truth for every compromise made because of
corporate-laptop restrictions (SSL inspection, no Rust toolchain, PowerShell
only). When you migrate this project to a personal machine, work through this
file top-to-bottom and every workaround will be resolved.

> **New since v3.0:** the project now includes a React frontend (`frontend/`). Node.js 18+ is required to build it. The frontend itself has no corporate-SSL workarounds — `npm install` and `npm run build` work on any machine with internet access.

> **New since v3.1:** a regression eval suite (`eval_dataset.json` + `test_regression_eval.py`) and GitHub Actions CI (`.github/workflows/tests.yml`) run on every push/PR. CI uses `requirements-ci.txt` (lean deps, Python 3.12) — no API keys needed.

> **New since v3.2:** an in-app **Evals** demo page (`app/routers/evals.py` + `frontend/src/pages/Evals.tsx`) with a live sandbox. It calls only the pure functions `route()` / `scan_input()` / `scan_output()` — **no LLM, no quota, no workarounds**, and works identically on any OS. If you only want to reproduce the *current* running system on a Mac (not the full production upgrade below), see [`SETUP_ON_MAC.md`](SETUP_ON_MAC.md).

---

## Environment Delta

| Restriction on Work Laptop | Work Laptop Workaround | Personal Laptop Target |
|---|---|---|
| Corporate SSL intercepts PyPI | `--trusted-host pypi.org --trusted-host files.pythonhosted.org` on every `pip install` | Bare `pip install -r requirements.txt` |
| `rustup` download blocked (SSL) → `maturin` fails → `litellm` uninstallable | `openai` SDK used instead of `litellm` | `pip install litellm`, flip `LLMProvider` adapter (see Module 2 below) |
| `httpx` SSL verification fails behind proxy | `httpx.AsyncClient(verify=False)` in `LLMProvider._make_client()` | Remove `verify=False`; use default `httpx.AsyncClient()` |
| No bash shell — PowerShell only | `;` to chain commands, `.\.venv\Scripts\` prefix on all executables | `&&` in bash; `source .venv/bin/activate` |
| `py` launcher present, bare `python` alias disabled | All commands use `py` or `.\.venv\Scripts\python.exe` | Use `python` or `python3` normally |
| Windows cp1252 terminal crashes on Unicode | All log/print output uses ASCII `[OK]` / `[WARN]` / `[ERROR]` | Unicode symbols (`✓`, `⚠`) safe to use |
| Docker Desktop not yet installed | SQLAlchemy models defined but no live Postgres; server starts with graceful warning | `docker compose up -d` — everything live |
| No Docker → no PostgreSQL | SQLite via `aiosqlite` (`gateway_dev.db` local file) | Change `DATABASE_URL` to `postgresql+asyncpg://...` in `.env` |
| No Docker → no ChromaDB container | `chromadb.PersistentClient` storing index in `./chromadb_data/` folder | Switch to `chromadb.HttpClient(host="localhost", port=8002)` |

---

## File-by-File Workaround Registry

### `app/services/llm_router.py`

**Workaround:** Using `openai` SDK instead of `litellm`.

**What to change on personal laptop:**
1. `pip install litellm`
2. In `LLMProvider._make_client()`: delete the `# OPENAI ONLY` block, uncomment the `# LITELLM` block.
3. In `LLMProvider.call()`: delete the `# OPENAI ONLY` block, uncomment the `# LITELLM` block.
4. In `LLMProvider.stream()`: delete the `# OPENAI ONLY` block, uncomment the `# LITELLM` block.
5. Remove `from openai import AsyncOpenAI, RateLimitError, APIStatusError` at the top.
6. Remove `import httpx` (no longer needed — litellm handles SSL/transport internally).
7. Delete `_make_client()` helper method entirely (litellm is provider-agnostic by model string).

**Result:** The `call_llm()` and `stream_llm()` module-level functions and all of
`proxy.py` remain completely unchanged.

---

### `requirements.txt`

**Workaround:** `litellm` is commented out; `openai` is used as a direct dependency.

**What to change on personal laptop:**
1. Uncomment `litellm>=1.0.0` (or install latest).
2. Comment out or remove `openai` (litellm bundles it).
3. Re-run: `pip install -r requirements.txt`

---

### All install commands in `README.md` and `PROGRESS.md`

**Workaround:** Every `pip install` includes `--trusted-host` flags.

**What to change on personal laptop:**
Strip the `--trusted-host pypi.org --trusted-host files.pythonhosted.org` suffix
from all documented install commands.

---

### `app/services/llm_router.py` — SSL verification

**Workaround:** `httpx.AsyncClient(verify=False)` is passed to every `AsyncOpenAI`
client to bypass corporate SSL certificate inspection.

**What to change on personal laptop:**
In `LLMProvider._make_client()`, change:
```python
# Remove this entire http_client= argument:
http_client=httpx.AsyncClient(verify=False),
```
(Moot if you also migrate to litellm, which handles this at its own layer.)

---

### `app/middleware/rate_limiter.py` — in-memory rate limit counter

**Workaround:** Redis is not running (no Docker). `get_redis_client()` pings Redis
on every request; if the ping fails it yields `None`. `check_rate_limit()` falls
back to a module-level dict keyed by `"{user_id}:{minute_bucket}"`.

**Limitations (local dev only):**
- Not persistent across server restarts
- Not shared across multiple uvicorn workers (single-process only)

**What to change on personal laptop:**
1. `docker compose up -d redis`
2. Nothing in the code changes — `get_redis_client()` will successfully ping Redis
   and yield the real client, activating the Redis pipeline path automatically.

---

### `app/db/session.py` — SQLite connection pool

**Workaround:** SQLite does not support `pool_size` / `max_overflow`. The engine
branches on the URL prefix:
- `sqlite+aiosqlite://...` → `StaticPool` + `check_same_thread=False`
- `postgresql+asyncpg://...` → full `pool_size=10, max_overflow=20`

**What to change on personal laptop:**
1. Set `DATABASE_URL=postgresql+asyncpg://gateway:gateway@localhost:5432/gateway` in `.env`.
2. The `else` branch in `session.py` is already correct — no code change needed.
3. Optionally delete the entire `if _is_sqlite:` block to keep the file clean.

---

### `app/db/models.py` — backend-agnostic UUID type

**Workaround:** Replaced `from sqlalchemy.dialects.postgresql import UUID` with
`from sqlalchemy import Uuid`. `sqlalchemy.Uuid` renders as `UUID` on PostgreSQL
and `CHAR(32)` on SQLite — the same Python `uuid.UUID` objects work with both.

**What to change on personal laptop:** Nothing. `sqlalchemy.Uuid` is correct for
both backends. The comment in models.py can be removed if desired.

---

### `app/services/cache.py` — local ChromaDB PersistentClient

**Workaround:** `chromadb.PersistentClient(path="./chromadb_data")` stores the
vector index in a local folder instead of the Docker ChromaDB container.
Uses `DefaultEmbeddingFunction` (ONNX, downloads from ChromaDB CDN) instead of
`sentence-transformers` (downloads from HuggingFace, blocked by corporate SSL).

**What to change on personal laptop:**
1. In `_ensure_ready()`: replace `chromadb.PersistentClient(path="./chromadb_data")`
   with `chromadb.HttpClient(host="localhost", port=8002)`.
2. Uncomment `sentence-transformers` in `requirements.txt` and switch to
   `SentenceTransformerEmbeddingFunction` (see comment in cache.py).
3. `docker compose up -d chromadb` — start the container.

---

### `app/services/document_ingestion.py` — restore markitdown on Mac/Linux

**Background:** On the work laptop (Python 3.14 + Windows) `markitdown`'s dependency
`magika` imports `onnxruntime` at module level, which triggers a Windows DLL
initialisation failure. The service was rewritten to use direct format-specific
libraries instead. On macOS/Linux `onnxruntime` loads correctly, so `markitdown`
can be restored for better conversion quality (links, tables, speaker notes,
Excel, ZIP, web URLs — all supported).

**What to change on personal laptop:**

Step 1 — `requirements.txt`:
- Uncomment `markitdown[pdf,docx,pptx]`
- Remove the five work-laptop-only lines (`pdfplumber`, `mammoth`, `python-pptx`, `beautifulsoup4`, `lxml`)
- Keep `python-multipart` (needed for FastAPI file upload on both platforms)

Step 2 — replace the entire contents of `app/services/document_ingestion.py` with:

```python
import os
import tempfile

_md = None  # lazy singleton — deferred import keeps server startup fast


def _get_md():
    global _md
    if _md is None:
        from markitdown import MarkItDown
        _md = MarkItDown()
    return _md


def ingest_document(file_bytes: bytes, filename: str) -> dict:
    suffix = os.path.splitext(filename)[1] or ".bin"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    try:
        result = _get_md().convert(tmp_path)
        return {
            "markdown": result.text_content,
            "original_bytes": len(file_bytes),
            "filename": filename,
        }
    finally:
        os.unlink(tmp_path)
```

The public API (`ingest_document(file_bytes, filename) -> dict`) is identical —
`app/routers/documents.py` and all callers require zero changes.

Step 3 — reinstall:
```bash
pip install markitdown[pdf,docx,pptx]
```

---

### Shell scripts / run commands

**Workaround:** All documented commands use PowerShell syntax.

**What to change on personal laptop:**

| PowerShell (work) | Bash (personal) |
|---|---|
| `.\.venv\Scripts\Activate.ps1` | `source .venv/bin/activate` |
| `.\.venv\Scripts\uvicorn.exe app.main:app` | `uvicorn app.main:app` |
| `.\.venv\Scripts\pytest.exe app/tests/` | `pytest app/tests/` |
| `cmd1 ; cmd2` | `cmd1 && cmd2` |
| `py -m venv .venv` | `python3 -m venv .venv` |


---

### Frontend (`frontend/`)

**No corporate-SSL workarounds needed.** `npm install` goes to the public npm registry, which is not intercepted by the corporate proxy on this machine.

**What to verify on personal laptop:**
1. `node --version` — must be 18+. Install via https://nodejs.org if needed.
2. `npm --version` — must be 9+. Comes bundled with Node.
3. `cd frontend && npm install && npm run dev` — should start Vite on port 5173 with no errors.

**Production build:**
```bash
cd frontend
npm run build       # outputs frontend/dist/
cd ..
uvicorn app.main:app --host 0.0.0.0 --port 8001
# FastAPI detects frontend/dist/ and mounts it at /
```

---

### `requirements-ci.txt` — lean CI dependency set

**Workaround:** Not a workaround — this is intentional. CI installs `requirements-ci.txt` instead of the full `requirements.txt` to avoid downloading `torch`, `transformers`, and `onnxruntime` (multi-GB) for packages that are lazily imported and never triggered by the test suite.

**What to change on personal laptop:** Nothing. Use `requirements.txt` for local dev; CI continues to use `requirements-ci.txt` automatically via `.github/workflows/tests.yml`.

---

### `app/routers/evals.py` — in-app Evals demo & sandbox

**No workarounds.** Exposes `/v1/evals/cases`, `/v1/evals/run-case`, and `/v1/evals/sandbox`, which run the pure `route()` / `scan_input()` / `scan_output()` functions. No LLM, no network, no API-key/quota usage, and no OS-specific behaviour.

**What to change on personal laptop:** Nothing. It works as-is on macOS/Linux. Registered via one line (`app.include_router(evals.router)`) in `app/main.py`; remove that line to roll back.

---

### `.github/workflows/tests.yml` — GitHub Actions CI

**No workarounds.** Runs `pytest app/tests/ -v` on Python 3.12 (Ubuntu). No secrets or API keys required.

**What to change on personal laptop:**
1. Push to GitHub and replace `<you>/<repo>` in the README badge URL with your actual org/repo.
2. Confirm the Actions tab shows the workflow passing on the first PR.

---

## Migration Checklist (execute in order on personal laptop)

- [ ] Clone repo / copy project files
- [ ] `python3 -m venv .venv && source .venv/bin/activate`
- [ ] Install Rust: `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`
- [ ] `pip install -r requirements.txt` (no `--trusted-host` flags needed)
- [ ] Verify `litellm` installed: `python -c "import litellm; print(litellm.__version__)"`
- [ ] In `app/services/llm_router.py`: uncomment `# LITELLM` lines, delete `# OPENAI ONLY` lines
- [ ] In `requirements.txt`: uncomment `litellm`, remove/comment `openai`
- [ ] In `LLMProvider._make_client()`: remove `httpx.AsyncClient(verify=False)`
- [ ] `docker compose up -d` — starts Postgres, Redis, ChromaDB (port 8002), Superset
- [ ] Copy `.env.example` → `.env`, fill in real API keys
- [ ] In `app/services/cache.py`: switch `PersistentClient` → `HttpClient(host="localhost", port=8002)`
- [ ] Restore markitdown: uncomment in `requirements.txt`, swap `document_ingestion.py` (see "Document Ingestion Restoration" section above), then `pip install markitdown[pdf,docx,pptx]`
- [ ] `uvicorn app.main:app --reload --port 8001`
- [ ] `pytest app/tests/ -v` — all **149 tests** should pass
- [ ] `pytest app/tests/test_regression_eval.py -v` — 61 golden eval cases (<1 s)
- [ ] Register user, create API key, fire first real LLM request
- [ ] `cd frontend && npm install && npm run build` — confirm dashboard builds
- [ ] Log in to dashboard at `http://127.0.0.1:8001` (or Vite dev server on 5173)
- [ ] Optional: `python demo_seed.py` to populate the live request feed
---

## Tested-On Reference

| Phase | Completed On | Python | OS | Notes |
|---|---|---|---|---|
| Phase 1 (scaffold + server) | 2026-07-19 | 3.14.5 (py launcher) | Windows 11 PowerShell | openai SDK, no Docker yet |
| Phase 1 (clean transition) | 2026-07-19 | 3.14.5 (py launcher) | Windows 11 PowerShell | LLMProvider adapter added |
| Dashboard UI | 2026-07-23 | 3.14.5 | Windows 11 PowerShell | 88 tests; Vite build passes |
| Regression eval + CI | 2026-07-23 | 3.14.5 (local) / 3.12 (CI) | Windows 11 / Ubuntu | 149 tests; golden dataset + GitHub Actions |