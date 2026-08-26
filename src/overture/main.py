"""ASGI entry point.

Run locally with: uvicorn overture.main:app --reload
"""

from fastapi import FastAPI

from overture.api.demo import router as demo_router
from overture.api.health import router as health_router
from overture.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Discovery-transcript to deployable tailored POC generator",
    version="0.1.0",
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
