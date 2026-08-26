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

app.include_router(health_router)
app.include_router(demo_router)
