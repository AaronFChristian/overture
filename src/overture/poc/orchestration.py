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
from collections.abc import Awaitable, Callable
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

# Optional progress callback: (stage_id, human_readable_detail) -> None.
# Optional on purpose -- the CLI passes nothing and behaves exactly as
# it always has, while the HTTP route passes one to stream real
# pipeline progress to the browser (D-0049). Any pipeline stage that
# doesn't emit is simply invisible to the UI rather than an error.
ProgressCallback = Callable[[str, str], Awaitable[None]]

# The canonical stage list, in execution order. The frontend renders
# these as a timeline; keeping the IDs here (rather than duplicated in
# the frontend) means a stage rename can't silently desync the two.
PIPELINE_STAGES: list[tuple[str, str]] = [
    ("extract", "Extracting requirements from the transcript"),
    ("classify", "Classifying each item's scope"),
    ("blueprint", "Selecting a demo blueprint"),
    ("compile", "Generating the demo configuration"),
    ("validate", "Validating the configuration"),
    ("persist", "Saving to Postgres"),
    ("index", "Embedding and indexing transcript chunks"),
    ("token", "Minting the share link"),
]


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
    on_progress: ProgressCallback | None = None,
) -> ExtractionOutcome:
    async def emit(stage: str, detail: str) -> None:
        if on_progress is not None:
            await on_progress(stage, detail)

    session_id = uuid.uuid4()

    # The graph internally runs extraction (4 parallel passes) and then
    # scope classification. Emitting both up front, rather than
    # threading a callback down into every LangGraph node, keeps the
    # graph's own code untouched -- see D-0049's rejected alternative.
    await emit("extract", "Running 4 parallel extraction passes")
    await emit("classify", "Batching items for scope classification")
    graph = build_graph(provider)
    result = await graph.ainvoke({"session_id": str(session_id), "transcript": transcript})
    brief = result["brief"]

    await emit("blueprint", f"Scoring blueprints against {len(brief.requirements)} items")
    blueprint = select_blueprint(brief)

    await emit("compile", f"Selected '{blueprint.name}' -- filling configuration")
    demo_config = await fill_config(brief, blueprint, provider)

    await emit("validate", "Running deterministic validation (no LLM)")
    demo_config = validate_config(demo_config)

    await emit("persist", "Writing session, requirements, and config")
    session_schema = DiscoverySession(id=session_id, raw_transcript=transcript)
    await persist_extraction_result(db, session_schema, brief)
    await persist_demo_config(db, demo_config)

    await emit("index", "Chunking and embedding the transcript")
    embedder = HashingEmbedder()
    chunks = await ingest_transcript(session_id, transcript, embedder)
    await persist_chunks(db, chunks)

    await emit("token", f"Indexed {len(chunks)} chunks")
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
