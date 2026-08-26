# syntax=docker/dockerfile:1

# --- Build stage --------------------------------------------------------
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

USER overture
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# No CMD-level shell, no health check baked in here -- Container
# Apps' own probe configuration (session 8 Terraform) handles health
# checking against GET /health, which already existed since session 1.
CMD ["uvicorn", "overture.main:app", "--host", "0.0.0.0", "--port", "8000"]
