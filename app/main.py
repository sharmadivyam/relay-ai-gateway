import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.db.models import Base
from app.db.session import engine
from app.routers import auth, proxy, documents, analytics, evals

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Attempt to create all tables on startup.
    # If Postgres is not yet running (e.g. Docker not started), log a warning
    # instead of crashing — the gateway will still serve /health.
    db_url = settings.database_url
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print(f"[OK] Database tables ready  ({db_url})")
    except Exception as exc:
        print(f"[WARN] Could not initialise database ({db_url}): {exc}")
        if "sqlite" in db_url:
            print("  Check that the project directory is writable.")
        else:
            print("  Start Docker and run: docker compose up -d postgres redis")
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    description="Production-grade AI Gateway with semantic caching, guardrails, and observability.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:8001",
        "http://localhost:8001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(proxy.router)
app.include_router(documents.router)
app.include_router(analytics.router)
app.include_router(evals.router)


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok", "service": settings.app_name}


# ── Static frontend (production deployment, option 1) ────────────────────────
# Mounted LAST so it never shadows /v1/*, /auth/*, or /health.
# Only activated when frontend/dist exists (i.e. after `npm run build`).
# In dev, the Vite dev server (port 5173) handles the frontend separately.
_FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(_FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=_FRONTEND_DIST, html=True), name="frontend")
