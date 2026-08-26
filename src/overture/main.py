"""ASGI entry point.

Run locally with: uvicorn overture.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from overture.api.demo import router as demo_router
from overture.api.health import router as health_router
from overture.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Discovery-transcript to deployable tailored POC generator",
    version="0.1.0",
)

# CORS: only enabled in local dev, and only for the Vite dev server's
# origin. In production the frontend and backend are served from the
# same Container App (D-0040's same-origin assumption), so cross-origin
# requests never happen there and this middleware is never added.
# Missing entirely until a real browser hit this route for the first
# time in session 9 -- FastAPI's TestClient and curl don't enforce
# CORS, so every prior verification of this route was blind to it.
# See decisions.md D-0044.
if settings.environment == "local":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

# Only wired when a real connection string is present -- see
# config.py's app_insights_connection_string. This keeps local dev
# and the entire test suite free of any Azure Monitor network call;
# `uv run pytest` never has this set, so this block never executes
# during CI or local development, only in the deployed container.
if settings.app_insights_connection_string:
    from azure.monitor.opentelemetry import configure_azure_monitor
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    configure_azure_monitor(connection_string=settings.app_insights_connection_string)
    FastAPIInstrumentor.instrument_app(app)

app.include_router(health_router)
app.include_router(demo_router)
