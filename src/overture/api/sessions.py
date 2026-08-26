"""SE console entry point -- HTTP-triggered extraction.

This is the route D-0013 anticipated ("Session 6, when the demo
runtime needs an HTTP-facing extraction trigger") -- arriving in
session 10 instead, once the SE console's frontend needed one. Shares
its core logic with the CLI via poc/orchestration.py so the two never
drift into different implementations of the same pipeline.

Auth: a simple shared-secret header, NOT real Entra ID/MSAL -- see
decisions.md D-0045. Real MSAL is blocked by D-0036's confirmed SDSU
tenant restriction; this is a placeholder appropriate for a
single-operator console, toggle-based the same way D-0037 handled
GitHub Actions OIDC (unset = disabled, the local-dev-friendly default).
"""

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from overture.config import get_settings
from overture.db.session import get_sessionmaker
from overture.poc.blueprints import ALL_BLUEPRINTS
from overture.poc.orchestration import run_extraction_pipeline
from overture.providers.factory import get_llm_provider

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


class ExtractRequest(BaseModel):
    transcript: str


class ExtractResponse(BaseModel):
    session_id: str
    summary: str
    requirement_counts: dict[str, int]
    scope_counts: dict[str, int]
    blueprint_id: str
    blueprint_name: str
    config_status: str
    validation_errors: list[str]
    sample_questions: list[str]
    demo_token: str | None
    chunks_indexed: int


def _check_console_auth(provided_secret: str | None) -> None:
    settings = get_settings()
    if settings.console_shared_secret is None:
        return  # auth disabled -- local dev default, see D-0045
    if provided_secret != settings.console_shared_secret:
        raise HTTPException(status_code=401, detail="Invalid or missing console secret.")


@router.post("/extract", response_model=ExtractResponse)
async def extract(
    body: ExtractRequest,
    x_console_secret: str | None = Header(default=None),
) -> ExtractResponse:
    _check_console_auth(x_console_secret)

    if not body.transcript.strip():
        raise HTTPException(status_code=422, detail="Transcript cannot be empty.")

    settings = get_settings()
    provider = get_llm_provider(settings)

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as db:
        outcome = await run_extraction_pipeline(
            transcript=body.transcript,
            provider=provider,
            db=db,
            share_token_secret=settings.share_token_secret,
        )
        await db.commit()

    requirement_counts: dict[str, int] = {}
    scope_counts: dict[str, int] = {}
    for req in outcome.brief.requirements:
        requirement_counts[req.category.value] = requirement_counts.get(req.category.value, 0) + 1
        scope_counts[req.scope.value] = scope_counts.get(req.scope.value, 0) + 1

    blueprint = next(
        (bp for bp in ALL_BLUEPRINTS if bp.id == outcome.demo_config.blueprint_id), None
    )
    blueprint_name = blueprint.name if blueprint else outcome.demo_config.blueprint_id

    return ExtractResponse(
        session_id=str(outcome.session_id),
        summary=outcome.brief.summary,
        requirement_counts=requirement_counts,
        scope_counts=scope_counts,
        blueprint_id=outcome.demo_config.blueprint_id,
        blueprint_name=blueprint_name,
        config_status=outcome.demo_config.status.value,
        validation_errors=outcome.demo_config.validation_errors,
        sample_questions=outcome.demo_config.sample_questions,
        demo_token=outcome.demo_token,
        chunks_indexed=outcome.chunk_count,
    )
