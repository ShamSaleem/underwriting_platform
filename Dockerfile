# ---------- Stage 1: build the React frontend ----------
FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
# Vite is configured to emit into ../backend/static; redirect it here instead.
RUN npm run build -- --outDir dist --emptyOutDir

# ---------- Stage 2: python runtime ----------
FROM python:3.12-slim AS app
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

COPY backend/requirements.txt ./
RUN pip install -r requirements.txt

# Backend code
COPY backend/ ./
# Built SPA from stage 1
COPY --from=web /web/dist ./static

# Cloud Run provides $PORT (default 8080). SQLite lives on the container's
# writable /tmp so it survives for the life of the instance.
ENV UW_DB_PATH=/tmp/underwriting.db
EXPOSE 8080
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
