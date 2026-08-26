"""Prospect-facing demo Q&A route.

Auth model: share-token only, no login (see poc/tokens.py D-0022).
This is the FIRST HTTP route in the codebase besides /health -- every
prior real entry point (sessions 4-5) was the CLI, deliberately, per
D-0013.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from overture.config import get_settings
from overture.db import models as db_models
from overture.db.session import get_db
from overture.poc.blueprints import ALL_BLUEPRINTS
from overture.poc.embeddings import HashingEmbedder
from overture.poc.retrieval import retrieve_top_chunks
from overture.poc.runtime import answer_question
from overture.poc.tokens import verify_share_token
from overture.providers.factory import get_llm_provider

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str
    citations: list[str]


class DemoConfigResponse(BaseModel):
    blueprint_id: str
    blueprint_name: str
    sample_questions: list[str]


async def _resolve_session_id(token: str) -> uuid.UUID:
    settings = get_settings()
    raw = verify_share_token(token, settings.share_token_secret)
    if raw is None:
        raise HTTPException(status_code=404, detail="This demo link is invalid or has expired.")
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="This demo link is invalid.") from exc


async def _load_demo_config(session_id: uuid.UUID, db: AsyncSession) -> db_models.DemoConfig:
    config_stmt = (
        select(db_models.DemoConfig)
        .where(db_models.DemoConfig.session_id == session_id)
        .order_by(db_models.DemoConfig.id.desc())
        .limit(1)
    )
    config_result = await db.execute(config_stmt)
    config_row = config_result.scalar_one_or_none()
    if config_row is None:
        raise HTTPException(status_code=404, detail="This demo hasn't been configured yet.")
    return config_row


@router.get("/{token}", response_model=DemoConfigResponse)
async def get_demo_config(
    token: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008 -- correct FastAPI DI idiom
) -> DemoConfigResponse:
    """What the frontend needs to render the demo page before the first question.

    Deliberately does NOT return `system_prompt` -- that's internal
    instruction text for the LLM, not something a prospect's browser
    needs or should see. `blueprint_name` is looked up from the fixed
    catalog (poc/blueprints.py), not stored redundantly on the row.
    """
    session_id = await _resolve_session_id(token)
    config_row = await _load_demo_config(session_id, db)

    blueprint = next(
        (bp for bp in ALL_BLUEPRINTS if bp.id == config_row.blueprint_id), None
    )
    blueprint_name = blueprint.name if blueprint else config_row.blueprint_id

    return DemoConfigResponse(
        blueprint_id=config_row.blueprint_id,
        blueprint_name=blueprint_name,
        sample_questions=list(config_row.sample_questions),
    )


@router.post("/{token}/ask", response_model=AskResponse)
async def ask(
    token: str,
    body: AskRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008 -- correct FastAPI DI idiom
) -> AskResponse:
    session_id = await _resolve_session_id(token)

    embedder = HashingEmbedder()
    query_embedding = await embedder.embed(body.question)

    chunks = await retrieve_top_chunks(db, session_id, query_embedding, top_k=3)
    if not chunks:
        raise HTTPException(
            status_code=404, detail="No content has been indexed for this demo yet."
        )

    config_row = await _load_demo_config(session_id, db)
    system_prompt = config_row.system_prompt

    provider = get_llm_provider()
    answer = await answer_question(
        question=body.question,
        system_prompt=system_prompt,
        chunks=[(chunk.chunk_index, chunk.text) for chunk in chunks],
        provider=provider,
    )

    return AskResponse(answer=answer, citations=[chunk.text for chunk in chunks])
