import uuid

import pytest

from overture.constants import EMBEDDING_DIM
from overture.poc.embeddings import HashingEmbedder
from overture.poc.ingestion import chunk_transcript, ingest_transcript


def test_chunk_transcript_splits_on_blank_lines() -> None:
    transcript = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    chunks = chunk_transcript(transcript)
    assert chunks == ["First paragraph.", "Second paragraph.", "Third paragraph."]


def test_chunk_transcript_with_no_blank_lines_returns_single_chunk() -> None:
    transcript = "Just one continuous block of text with no paragraph breaks."
    chunks = chunk_transcript(transcript)
    assert chunks == [transcript]


def test_chunk_transcript_strips_whitespace() -> None:
    transcript = "  Padded first.  \n\n  Padded second.  "
    chunks = chunk_transcript(transcript)
    assert chunks == ["Padded first.", "Padded second."]


@pytest.mark.asyncio
async def test_ingest_transcript_produces_one_chunk_schema_per_paragraph() -> None:
    session_id = uuid.uuid4()
    transcript = "Pain one here.\n\nConstraint one here.\n\nRequirement one here."
    embedder = HashingEmbedder()

    chunks = await ingest_transcript(session_id, transcript, embedder)

    assert len(chunks) == 3
    assert [c.chunk_index for c in chunks] == [0, 1, 2]
    assert all(c.session_id == session_id for c in chunks)
    assert all(len(c.embedding) == EMBEDDING_DIM for c in chunks)
    assert chunks[0].text == "Pain one here."
