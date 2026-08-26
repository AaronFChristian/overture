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
from overture.db.session import get_sessionmaker
from overture.poc.blueprints import ALL_BLUEPRINTS
from overture.poc.embeddings import HashingEmbedder
from overture.poc.orchestration import run_extraction_pipeline
from overture.poc.retrieval import retrieve_top_chunks
from overture.poc.runtime import answer_question
from overture.poc.tokens import verify_share_token
from overture.providers.factory import get_llm_provider


async def run_extract(transcript_path: Path) -> None:
    settings = get_settings()
    transcript = transcript_path.read_text(encoding="utf-8")

    print(f"Provider: {settings.llm_provider}")
    print(f"Source:   {transcript_path}")
    print("Running extraction graph...\n")

    provider = get_llm_provider(settings)

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as db:
        outcome = await run_extraction_pipeline(
            transcript=transcript,
            provider=provider,
            db=db,
            share_token_secret=settings.share_token_secret,
        )
        await db.commit()

    print(f"Session:  {outcome.session_id}")
    print(outcome.brief.summary)
    print()
    for req in outcome.brief.requirements:
        print(f"[{req.category.value:12}] [{req.scope.value:20}] {req.text}")
        print(f'    source: "{req.source_span.quoted_text}"')
    print()

    blueprint = next(
        (bp for bp in ALL_BLUEPRINTS if bp.id == outcome.demo_config.blueprint_id), None
    )
    blueprint_name = blueprint.name if blueprint else outcome.demo_config.blueprint_id
    print(f"Selected blueprint: {outcome.demo_config.blueprint_id} ({blueprint_name})")

    print(f"Config status: {outcome.demo_config.status.value}")
    if outcome.demo_config.validation_errors:
        for error in outcome.demo_config.validation_errors:
            print(f"  - {error}")
    else:
        print(f"System prompt: {outcome.demo_config.system_prompt}")
        print("Sample questions:")
        for question in outcome.demo_config.sample_questions:
            print(f"  - {question}")
    print()

    print(
        f"Persisted to database as session {outcome.session_id} "
        f"({outcome.chunk_count} chunks indexed)"
    )

    if outcome.demo_token:
        print(f"Demo link token: {outcome.demo_token}")
        print(f'  overture ask {outcome.demo_token} "your question here"')


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
