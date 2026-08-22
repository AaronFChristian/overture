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

from overture.config import get_settings
from overture.db.repository import persist_demo_config, persist_extraction_result
from overture.db.session import get_sessionmaker
from overture.graph.builder import build_graph
from overture.poc.compiler import fill_config, select_blueprint
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
        await db.commit()

    print(f"Persisted to database as session {session_id}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="overture")
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract_parser = subparsers.add_parser("extract", help="Run extraction on a transcript file")
    extract_parser.add_argument("transcript", type=Path, help="Path to a transcript .txt file")

    args = parser.parse_args()

    if args.command == "extract":
        transcript_path: Path = args.transcript
        if not transcript_path.exists():
            print(f"File not found: {transcript_path}", file=sys.stderr)
            sys.exit(1)
        asyncio.run(run_extract(transcript_path))


if __name__ == "__main__":
    main()
