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

import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from overture.config import get_settings
from overture.db.session import get_sessionmaker
from overture.poc.blueprints import ALL_BLUEPRINTS
from overture.poc.orchestration import (
    PIPELINE_STAGES,
    ExtractionOutcome,
    run_extraction_pipeline,
)
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


def _build_response(outcome: ExtractionOutcome) -> "ExtractResponse":
    """Shared by both the plain and the streaming route.

    Kept as one function for the same reason D-0046 factored the
    pipeline itself: two routes returning "the same" response shape
    is exactly how two shapes quietly drift apart.
    """
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


@router.get("/stages")
async def list_stages() -> list[dict[str, str]]:
    """The canonical pipeline stage list, so the frontend can render
    the full timeline up front (greyed out) rather than having stages
    pop into existence as they complete. Served from the same
    PIPELINE_STAGES constant the pipeline itself emits against, so
    the two can't desync -- see D-0049."""
    return [{"id": sid, "label": label} for sid, label in PIPELINE_STAGES]


@router.post("/extract/stream")
async def extract_stream(
    body: ExtractRequest,
    x_console_secret: str | None = Header(default=None),
) -> StreamingResponse:
    """Server-Sent Events version of /extract.

    Emits one `progress` event per pipeline stage as it starts, then a
    final `result` event with the same payload /extract returns, or an
    `error` event if the pipeline raises. See decisions.md D-0049.
    """
    _check_console_auth(x_console_secret)

    if not body.transcript.strip():
        raise HTTPException(status_code=422, detail="Transcript cannot be empty.")

    async def event_stream() -> AsyncGenerator[str, None]:
        # The pipeline runs as a task while this generator yields
        # whatever lands on the queue -- the pipeline can't yield
        # directly (it's a plain async function, not a generator), so
        # a queue is what bridges "callback that fires mid-pipeline"
        # to "generator that yields to the HTTP response."
        queue: asyncio.Queue[tuple[str, str] | None] = asyncio.Queue()

        async def on_progress(stage: str, detail: str) -> None:
            await queue.put((stage, detail))

        settings = get_settings()
        provider = get_llm_provider(settings)
        sessionmaker = get_sessionmaker()

        outcome_result: ExtractionOutcome | None = None
        error_result: str | None = None

        async def run() -> None:
            nonlocal outcome_result, error_result
            try:
                async with sessionmaker() as db:
                    outcome = await run_extraction_pipeline(
                        transcript=body.transcript,
                        provider=provider,
                        db=db,
                        share_token_secret=settings.share_token_secret,
                        on_progress=on_progress,
                    )
                    await db.commit()
                outcome_result = outcome
            except Exception as exc:  # noqa: BLE001 -- surfaced to the client below
                error_result = str(exc)
            finally:
                await queue.put(None)  # sentinel: pipeline finished

        task = asyncio.create_task(run())

        while True:
            item = await queue.get()
            if item is None:
                break
            stage, detail = item
            yield f"event: progress\ndata: {json.dumps({'stage': stage, 'detail': detail})}\n\n"

        await task

        if error_result is not None:
            yield f"event: error\ndata: {json.dumps({'detail': error_result})}\n\n"
        elif outcome_result is not None:
            payload = _build_response(outcome_result).model_dump()
            yield f"event: result\ndata: {json.dumps(payload)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            # Without this, a proxy sitting in front of the app (Azure
            # Container Apps' ingress, for instance) may buffer the
            # whole response and defeat the point of streaming
            # entirely -- the browser would get every event at once,
            # at the end. Untested through Azure's ingress until a
            # real deploy; see D-0049's revisit note.
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


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

    return _build_response(outcome)
