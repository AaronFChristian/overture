import pytest

from overture.constants import EMBEDDING_DIM
from overture.poc.embeddings import HashingEmbedder
from overture.poc.retrieval import cosine_similarity


@pytest.mark.asyncio
async def test_embed_produces_correct_dimension() -> None:
    embedder = HashingEmbedder()
    vector = await embedder.embed("Legal review takes three weeks")
    assert len(vector) == EMBEDDING_DIM


@pytest.mark.asyncio
async def test_embed_is_deterministic() -> None:
    embedder = HashingEmbedder()
    v1 = await embedder.embed("SharePoint contract storage")
    v2 = await embedder.embed("SharePoint contract storage")
    assert v1 == v2


@pytest.mark.asyncio
async def test_embed_is_normalized() -> None:
    embedder = HashingEmbedder()
    vector = await embedder.embed("some reasonably long piece of text to embed")
    norm = sum(v * v for v in vector) ** 0.5
    assert abs(norm - 1.0) < 1e-9


@pytest.mark.asyncio
async def test_empty_text_produces_zero_vector_not_a_crash() -> None:
    embedder = HashingEmbedder()
    vector = await embedder.embed("")
    assert vector == [0.0] * EMBEDDING_DIM


@pytest.mark.asyncio
async def test_similar_text_scores_higher_than_dissimilar_text() -> None:
    embedder = HashingEmbedder()
    query = await embedder.embed("How long does legal review take for contracts?")
    similar = await embedder.embed("Legal review of every contract renewal takes three weeks")
    dissimilar = await embedder.embed("The German joint venture has separate systems entirely")

    similar_score = cosine_similarity(query, similar)
    dissimilar_score = cosine_similarity(query, dissimilar)

    assert similar_score > dissimilar_score


@pytest.mark.asyncio
async def test_custom_dimension_is_respected() -> None:
    embedder = HashingEmbedder(dim=64)
    vector = await embedder.embed("test")
    assert len(vector) == 64
