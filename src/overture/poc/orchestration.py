"""Shared extraction pipeline orchestration.

Used by both `overture extract` (the CLI, D-0013) and
`POST /api/v1/sessions/extract` (the new HTTP route, session 10) --
factored out here specifically so the two never drift into two
different implementations of the same pipeline. This is the route
D-0013 always anticipated ("Session 6, when the demo runtime needs an
HTTP-facing extraction trigger") -- it arrived in session 10 instead,
once the SE console's frontend actually needed one.

Does not call `db.commit()` -- same contract as
`db/repository.py::persist_extraction_result`: the caller controls
the transaction boundary.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from overture.db.repository import persist_chunks, persist_demo_config, persist_extraction_result
from overture.graph.builder import build_graph
from overture.poc.compiler import fill_config, select_blueprint
from overture.poc.embeddings import HashingEmbedder
from overture.poc.ingestion import ingest_transcript
from overture.poc.tokens import mint_share_token
from overture.poc.validator import validate_config
from overture.providers.base import LLMProvider
from overture.schemas import DemoConfig, DiscoverySession, SolutionBrief


@dataclass
class ExtractionOutcome:
    session_id: uuid.UUID
    brief: SolutionBrief
    demo_config: DemoConfig
    chunk_count: int
    demo_token: str | None


async def run_extraction_pipeline(
    *,
    transcript: str,
    provider: LLMProvider,
    db: AsyncSession,
    share_token_secret: str,
) -> ExtractionOutcome:
    session_id = uuid.uuid4()

    graph = build_graph(provider)
    result = await graph.ainvoke({"session_id": str(session_id), "transcript": transcript})
    brief = result["brief"]

    blueprint = select_blueprint(brief)
    demo_config = await fill_config(brief, blueprint, provider)
    demo_config = validate_config(demo_config)

    session_schema = DiscoverySession(id=session_id, raw_transcript=transcript)
    await persist_extraction_result(db, session_schema, brief)
    await persist_demo_config(db, demo_config)

    embedder = HashingEmbedder()
    chunks = await ingest_transcript(session_id, transcript, embedder)
    await persist_chunks(db, chunks)

    demo_token = None
    if demo_config.status.value == "validated":
        demo_token = mint_share_token(str(session_id), share_token_secret)

    return ExtractionOutcome(
        session_id=session_id,
        brief=brief,
        demo_config=demo_config,
        chunk_count=len(chunks),
        demo_token=demo_token,
    )
