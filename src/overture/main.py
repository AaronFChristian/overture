"""ASGI entry point.

Run locally with: uvicorn overture.main:app --reload
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from overture.api.demo import router as demo_router
from overture.api.health import router as health_router
from overture.api.sessions import router as sessions_router
from overture.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Discovery-transcript to deployable tailored POC generator",
    version="0.1.0",
)

# CORS: only enabled in local dev, and only for the Vite dev server's
# origin. In production the frontend and backend are served from the
# same Container App (D-0040's same-origin assumption, actually
# executed in D-0047), so cross-origin requests never happen there and
# this middleware is never added. Missing entirely until a real
# browser hit this route for the first time in session 9 -- FastAPI's
# TestClient and curl don't enforce CORS, so every prior verification
# of this route was blind to it. See decisions.md D-0044.
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
app.include_router(sessions_router)

# --- Frontend serving (only present in the deployed container) -----------
# The Dockerfile copies the frontend's built `dist/` here as
# `static/`, ONLY at image build time -- local `uvicorn --reload` has
# no such directory, so this whole block is skipped and local dev
# behaves exactly as it always has (frontend served separately via
# `npm run dev`). Registered LAST, after every API router: Starlette
# resolves routes in registration order, so /health and /api/v1/...
# always win over the catch-all below, even though the catch-all's
# path pattern would otherwise match them too. See decisions.md D-0047.
_static_dir = Path(__file__).parent / "static"
if _static_dir.exists():
    app.mount("/assets", StaticFiles(directory=_static_dir / "assets"), name="frontend-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str) -> FileResponse:
        # Always serve index.html, regardless of the requested path --
        # this is what makes client-side routes (React Router's
        # /demo/:token, /console) work correctly on a direct page
        # load or a browser refresh, not just on in-app navigation.
        return FileResponse(_static_dir / "index.html")
