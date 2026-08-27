# syntax=docker/dockerfile:1

# --- Frontend build stage -------------------------------------------------
# Builds the React app with VITE_API_BASE_URL explicitly empty, so the
# built bundle makes same-origin relative requests (/api/v1/...)
# instead of pointing at localhost:8000 -- the frontend is served from
# the SAME Container App as the API in production (D-0040's original
# plan, only actually executed here). See decisions.md D-0047.
FROM --platform=linux/amd64 node:22-slim AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN VITE_API_BASE_URL= npm run build

# --- Backend build stage --------------------------------------------------
# uv installs into a venv here; only that venv gets copied into the
# final stage, not uv itself or any build tooling.
#
# --platform=linux/amd64 pinned explicitly: without it, building on
# an Apple Silicon Mac produces an arm64 image that Azure Container
# Apps (amd64-only infrastructure) cannot run at all -- discovered via
# a real failed deploy, not anticipated. See decisions.md D-0039.
# scripts/manual-deploy.sh also passes --platform linux/amd64 on the
# `docker build` invocation; both together make this correct
# regardless of how the build is triggered.
FROM --platform=linux/amd64 python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /bin/

WORKDIR /app

# Copy dependency manifests first, before app code -- Docker layer
# caching means `uv sync` only re-runs when pyproject.toml/uv.lock
# actually change, not on every code edit.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY src/ ./src/
RUN uv sync --frozen --no-dev

# --- Runtime stage --------------------------------------------------------
FROM --platform=linux/amd64 python:3.12-slim AS runtime

# Runs as a non-root user -- no reason a web process needs root, and
# Container Apps has no requirement that it does.
RUN useradd --create-home --shell /bin/bash overture
WORKDIR /app

COPY --from=builder --chown=overture:overture /app/.venv /app/.venv
COPY --from=builder --chown=overture:overture /app/src /app/src
# Built frontend assets -- main.py checks whether this directory
# exists at import time and only mounts static-file serving if it
# does, so local `uvicorn --reload` (no built frontend present)
# behaves exactly as before. See decisions.md D-0047.
COPY --from=frontend-builder --chown=overture:overture /app/frontend/dist /app/src/overture/static

USER overture
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# No CMD-level shell, no health check baked in here -- Container
# Apps' own probe configuration (session 8 Terraform) handles health
# checking against GET /health, which already existed since session 1.
CMD ["uvicorn", "overture.main:app", "--host", "0.0.0.0", "--port", "8000"]
