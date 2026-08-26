"""Ingestion -- turns a raw transcript into embedded, persistable Chunks.

Chunking reuses text_utils.split_paragraphs -- the same rule the
extraction graph's segment() node uses, so "what counts as one chunk"
means the same thing everywhere in this codebase, not two slightly
different definitions that happen to look similar.
"""

import uuid

from overture.poc.embeddings import Embedder
from overture.schemas import Chunk
from overture.text_utils import split_paragraphs


def chunk_transcript(transcript: str) -> list[str]:
    return split_paragraphs(transcript)


async def ingest_transcript(
    session_id: uuid.UUID, transcript: str, embedder: Embedder
) -> list[Chunk]:
    texts = chunk_transcript(transcript)
    chunks: list[Chunk] = []
    for index, text in enumerate(texts):
        embedding = await embedder.embed(text)
        chunks.append(
            Chunk(session_id=session_id, chunk_index=index, text=text, embedding=embedding)
        )
    return chunks
