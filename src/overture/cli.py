"""CLI entry point.

Usage:
    uv run overture extract path/to/transcript.txt

This is deliberately the FIRST real entry point into the extraction
graph and the FIRST thing that writes to the database -- see
decisions.md D-0013 for why a CLI came before an HTTP route. Every
run of `extract` does two things a route wouldn't make as visible:
prints every extracted Requirement with its source quote directly to
the terminal (so a bad extraction is obvious immediately, not buried
in a JSON response), and persists the full result to Postgres.
"""

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

from sqlalchemy import select

from overture.config import get_settings
from overture.db import models as db_models
from overture.db.repository import persist_chunks, persist_demo_config, persist_extraction_result
from overture.db.session import get_sessionmaker
from overture.graph.builder import build_graph
from overture.poc.compiler import fill_config, select_blueprint
from overture.poc.embeddings import HashingEmbedder
from overture.poc.ingestion import ingest_transcript
from overture.poc.retrieval import retrieve_top_chunks
from overture.poc.runtime import answer_question
from overture.poc.tokens import mint_share_token, verify_share_token
from overture.poc.validator import validate_config
from overture.providers.factory import get_llm_provider
from overture.schemas import DiscoverySession as DiscoverySessionSchema


async def run_extract(transcript_path: Path) -> None:
    settings = get_settings()
    transcript = transcript_path.read_text(encoding="utf-8")
    session_id = uuid.uuid4()

    print(f"Provider: {settings.llm_provider}")
    print(f"Session:  {session_id}")
    print(f"Source:   {transcript_path}")
    print("Running extraction graph...\n")

    provider = get_llm_provider(settings)
    graph = build_graph(provider)

    result = await graph.ainvoke({"session_id": str(session_id), "transcript": transcript})
    brief = result["brief"]

    print(brief.summary)
    print()
    for req in brief.requirements:
        print(f"[{req.category.value:12}] [{req.scope.value:20}] {req.text}")
        print(f'    source: "{req.source_span.quoted_text}"')
    print()

    blueprint = select_blueprint(brief)
    print(f"Selected blueprint: {blueprint.id} ({blueprint.name})")
    demo_config = await fill_config(brief, blueprint, provider)
    demo_config = validate_config(demo_config)

    print(f"Config status: {demo_config.status.value}")
    if demo_config.validation_errors:
        for error in demo_config.validation_errors:
            print(f"  - {error}")
    else:
        print(f"System prompt: {demo_config.system_prompt}")
        print("Sample questions:")
        for question in demo_config.sample_questions:
            print(f"  - {question}")
    print()

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as db:
        session_schema = DiscoverySessionSchema(id=session_id, raw_transcript=transcript)
        await persist_extraction_result(db, session_schema, brief)
        await persist_demo_config(db, demo_config)

        embedder = HashingEmbedder()
        chunks = await ingest_transcript(session_id, transcript, embedder)
        await persist_chunks(db, chunks)

        await db.commit()

    print(f"Persisted to database as session {session_id} ({len(chunks)} chunks indexed)")

    if demo_config.status.value == "validated":
        token = mint_share_token(str(session_id), settings.share_token_secret)
        print(f"Demo link token: {token}")
        print(f'  overture ask {token} "your question here"')


async def run_ask(token: str, question: str) -> None:
    settings = get_settings()
    session_id_str = verify_share_token(token, settings.share_token_secret)
    if session_id_str is None:
        print("This demo link is invalid or has expired.", file=sys.stderr)
        sys.exit(1)
    session_id = uuid.UUID(session_id_str)

    provider = get_llm_provider(settings)
    embedder = HashingEmbedder()
    query_embedding = await embedder.embed(question)

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as db:
        chunks = await retrieve_top_chunks(db, session_id, query_embedding, top_k=3)
        if not chunks:
            print("No content has been indexed for this session.", file=sys.stderr)
            sys.exit(1)

        config_stmt = (
            select(db_models.DemoConfig)
            .where(db_models.DemoConfig.session_id == session_id)
            .order_by(db_models.DemoConfig.id.desc())
            .limit(1)
        )
        config_result = await db.execute(config_stmt)
        config_row = config_result.scalar_one_or_none()
        system_prompt = config_row.system_prompt if config_row else ""

    answer = await answer_question(
        question=question,
        system_prompt=system_prompt,
        chunks=[(chunk.chunk_index, chunk.text) for chunk in chunks],
        provider=provider,
    )

    print(answer)
    print()
    print("Retrieved context:")
    for chunk in chunks:
        print(f"  - {chunk.text}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="overture")
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract_parser = subparsers.add_parser("extract", help="Run extraction on a transcript file")
    extract_parser.add_argument("transcript", type=Path, help="Path to a transcript .txt file")

    ask_parser = subparsers.add_parser("ask", help="Ask a question against an ingested session")
    ask_parser.add_argument("token", help="Demo share token, printed at the end of `extract`")
    ask_parser.add_argument("question", help="The question to ask")

    args = parser.parse_args()

    if args.command == "extract":
        transcript_path: Path = args.transcript
        if not transcript_path.exists():
            print(f"File not found: {transcript_path}", file=sys.stderr)
            sys.exit(1)
        asyncio.run(run_extract(transcript_path))
    elif args.command == "ask":
        asyncio.run(run_ask(args.token, args.question))


if __name__ == "__main__":
    main()
