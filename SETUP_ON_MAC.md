# Transfer to Mac & Run — Step-by-Step

This guide takes you from **zipping the project on the Windows work laptop** to
**running the exact current system on your personal Mac** — backend + dashboard
(including the new **Evals** page and live sandbox) working end-to-end.

It reproduces the *current* dev setup (SQLite, in-memory rate limiter, `openai`
SDK against Cerebras, no Docker). For the full production upgrade (PostgreSQL,
Redis, ChromaDB container, litellm), do this first, then follow
[`MIGRATION_GUIDE.md`](MIGRATION_GUIDE.md).

---

## Part A — Make the zip (on Windows, PowerShell)

Dependencies are **not** included in the zip — you will reinstall them on the Mac
(`pip install` + `npm install`). We exclude the virtualenv, `node_modules`, build
output, caches, and the local database so the archive stays small (a few MB).

```powershell
# Run from the folder that CONTAINS my_proj
cd C:\Users\divyam.sharma\Downloads

$src   = "C:\Users\divyam.sharma\Downloads\my_proj"
$stage = "C:\Users\divyam.sharma\Downloads\my_proj_transfer"

# 1. Stage a clean copy, skipping everything that gets regenerated on the Mac.
#    /XD = exclude directories (matched by name at any depth)
#    /XF = exclude files
robocopy $src $stage /E `
  /XD ".venv" "node_modules" "dist" "__pycache__" ".pytest_cache" ".git" "chromadb_data" ".mypy_cache" `
  /XF "gateway_dev.db" "*.pyc"

# 2. Compress the staged copy into a single zip.
Compress-Archive -Path "$stage\*" -DestinationPath "C:\Users\divyam.sharma\Downloads\my_proj.zip" -Force

# 3. Remove the staging folder (the zip is all you need).
Remove-Item -Recurse -Force $stage
```

`robocopy` prints a summary table when it finishes — that is normal, not an error
(exit codes 0-7 all mean success).

### What is excluded and why

| Excluded | Why it's safe to drop |
|---|---|
| `.venv/` | Python packages — reinstalled via `pip install -r requirements.txt` on the Mac |
| `frontend/node_modules/` | Node packages — reinstalled via `npm install` |
| `frontend/dist/` | Built frontend — regenerated via `npm run build` (or served by Vite in dev) |
| `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/` | Regenerated automatically |
| `chromadb_data/` | Local vector index — recreated on first use |
| `gateway_dev.db` | SQLite DB — a fresh empty one is created on first startup |
| `.git/` | Version history — optional; drop it to keep the zip small |

### About `.env` (your secrets)

The staging copy **includes `.env`** (it does not match any exclude rule), so your
API keys travel with the zip and the app works immediately on the Mac. Because it
contains secrets, keep the zip private (do not upload it anywhere public).

If you would rather not ship secrets, add `/XF ".env"` to the `robocopy` line
above, then recreate it on the Mac by copying `.env.example` to `.env` and filling
in your keys (see Part B, step 4).

---

## Part B — Set up and run (on the Mac, Terminal)

### 0. Install prerequisites (one time)

Install [Homebrew](https://brew.sh) if you don't have it, then:

```bash
brew install python@3.12 node
python3 --version   # 3.12 or newer
node --version      # 18 or newer
```

### 1. Unzip

```bash
cd ~/Downloads
unzip my_proj.zip -d my_proj
cd my_proj
```

(If the zip expands with a nested folder, `cd` into the one that contains
`app/`, `frontend/`, and `requirements.txt`.)

### 2. Create the Python virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Your prompt should now start with `(.venv)`. On the Mac you use `python`/`pip`
directly (no `py` launcher, no `.\.venv\Scripts\` prefix, no `--trusted-host`
flags — those were Windows/corporate-only).

### 3. Install Python dependencies

Full install (matches the current system — includes semantic cache, compression,
and document ingestion support):

```bash
pip install -r requirements.txt
```

> Tip: `requirements.txt` pulls in `llmlingua` (torch/transformers, several
> hundred MB). If you only want the dashboard + Evals + chat + routing/guardrails
> and a faster install, use the lean set instead:
>
> ```bash
> pip install -r requirements-ci.txt
> ```
>
> The Evals page, sandbox, routing, and guardrails all work on the lean set
> because they call pure Python functions. (Document ingestion and the semantic
> cache need the full `requirements.txt`.)

### 4. Configure `.env`

If you included `.env` in the zip, skip this step — it's already there.

Otherwise:

```bash
cp .env.example .env
```

Then open `.env` and set at least:

```env
OPENAI_API_KEY=<your Cerebras/OpenAI key>
JWT_SECRET_KEY=<any long random string>
```

The defaults for everything else already match the current setup
(`PRIMARY_MODEL=gpt-oss-120b`, SQLite database, feature flags off). On the Mac you
can optionally set `ENABLE_SEMANTIC_CACHE=true` (it was disabled on Windows only).

### 5. Start the backend (Terminal 1)

```bash
source .venv/bin/activate     # if not already active
uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Wait for `Application startup complete`. Quick check in another shell:

```bash
curl http://127.0.0.1:8001/health          # -> {"status":"ok",...}
curl -i http://127.0.0.1:8001/v1/evals/cases   # -> HTTP/1.1 401 (route exists, needs login)
```

Swagger UI: **http://127.0.0.1:8001/docs**

### 6. Start the dashboard (Terminal 2)

```bash
cd frontend
npm install
npm run dev
```

Vite prints a `Local:` URL — usually **http://localhost:5173** (it picks the next
free port, e.g. 5174, if 5173 is busy). The dev server proxies `/v1` and `/auth`
to the backend on port 8001, so no CORS setup is needed.

### 7. Use it

1. Open the dashboard URL from step 6.
2. Register an account, then log in.
3. Open the **Evals** tab:
   - Click **Run evals** — the 9 curated cases tick through one-by-one, all green.
   - Expand any case with **View proof** to see the exact input, before/after
     redaction, the matched rule/reason, and the raw API JSON.
   - Open **Try your own case**, pick a mode, type anything (e.g. a made-up SSN),
     and hit **Run** to prove results are computed live, not hardcoded.

---

## Optional — verify the test suite

```bash
source .venv/bin/activate
pytest app/tests/ -v                          # full suite
pytest app/tests/test_regression_eval.py -v   # 61 golden eval cases, <1s, no LLM
```

---

## Optional — production build (single process)

Serve the dashboard from FastAPI instead of the Vite dev server:

```bash
cd frontend
npm run build          # outputs frontend/dist/
cd ..
uvicorn app.main:app --host 0.0.0.0 --port 8001
# open http://127.0.0.1:8001  (FastAPI auto-mounts frontend/dist at /)
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Dashboard shows "Could not load eval cases" | Backend isn't running or still starting — confirm step 5 shows `Application startup complete`, then refresh. |
| `curl /v1/evals/cases` returns 404 | You're running an old backend build. Stop it and restart `uvicorn` from the project root. |
| Vite starts on 5174 instead of 5173 | Port 5173 is in use by another dev server; just open the URL Vite prints. |
| `pip install` fails compiling `llmlingua`/torch | Use `pip install -r requirements-ci.txt` (see step 3 tip) — Evals/chat/dashboard still work. |
| `command not found: python3` | Reopen Terminal after `brew install python@3.12`, or use the full brew path. |
| Login works but requests error | Make sure `OPENAI_API_KEY` in `.env` is valid; the Evals page itself needs no key. |

Everything beyond this (PostgreSQL, Redis, ChromaDB container, litellm, Superset)
is covered in [`MIGRATION_GUIDE.md`](MIGRATION_GUIDE.md).
