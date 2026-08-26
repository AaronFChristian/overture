"""Retrieval.

`rank_by_similarity` is pure -- no DB, no network -- and unit tested
directly (see tests/poc/test_retrieval.py). `retrieve_top_chunks`
touches a live AsyncSession via pgvector's cosine_distance comparator
and can only be proven against real Postgres -- same pure/impure split
already used for persistence (D-0005-adjacent pattern) and the Alembic
migration.
"""

import math
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from overture.db import models as db_models


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"vector length mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def rank_by_similarity(
    query_embedding: list[float],
    candidates: list[tuple[str, list[float]]],
    top_k: int = 3,
) -> list[tuple[str, float]]:
    """Rank (text, embedding) candidates by similarity to a query embedding.

    Returns (text, score) pairs, highest score first, truncated to
    top_k. This is the algorithm pgvector's cosine_distance ordering
    implements at the database level -- kept as a pure function here
    so the ranking logic itself is testable without a database.
    """
    scored = [(text, cosine_similarity(query_embedding, emb)) for text, emb in candidates]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:top_k]


async def retrieve_top_chunks(
    db: AsyncSession,
    session_id: uuid.UUID,
    query_embedding: list[float],
    top_k: int = 3,
) -> list[db_models.Chunk]:
    """Live pgvector query -- the DB-touching counterpart to rank_by_similarity above."""
    stmt = (
        select(db_models.Chunk)
        .where(db_models.Chunk.session_id == session_id)
        .order_by(db_models.Chunk.embedding.cosine_distance(query_embedding))
        .limit(top_k)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
