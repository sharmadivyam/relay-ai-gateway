# ── Stage 1: build the React dashboard ─────────────────────────────────────
FROM node:20-slim AS frontend-builder

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build
# → produces /build/dist

# ── Stage 2: backend runtime, serving the built dashboard ──────────────────
FROM python:3.12-slim

# build-essential: some transitive deps (e.g. via sentence-transformers/torch)
# may need to compile if no prebuilt wheel matches this exact platform/Python
# combo — matters especially on arm64 (Oracle Ampere A1), where prebuilt
# wheel coverage is less universal than linux/amd64.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps first (separate layer) so `docker build` reuses this layer
# on every rebuild where only application code changed, not requirements.txt.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Backend app code
COPY app ./app

# Built dashboard, straight from stage 1 — lands at /app/frontend/dist,
# which is exactly where main.py's _FRONTEND_DIST lookup expects it
# (os.path.join(dirname(__file__), "..", "frontend", "dist") from app/main.py
# resolves to /app/frontend/dist given WORKDIR /app and COPY app ./app above).
COPY --from=frontend-builder /build/dist ./frontend/dist

EXPOSE 8001

# Railway/Render inject $PORT dynamically; 8001 is the fallback for local
# `docker run` / `docker compose` testing, and for Oracle Cloud where you
# control the port mapping yourself via Caddy.
ENV PORT=8001

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]

