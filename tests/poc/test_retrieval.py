import pytest

from overture.poc.retrieval import cosine_similarity, rank_by_similarity


def test_cosine_similarity_identical_vectors_is_one() -> None:
    v = [1.0, 0.0, 0.0]
    assert abs(cosine_similarity(v, v) - 1.0) < 1e-9


def test_cosine_similarity_orthogonal_vectors_is_zero() -> None:
    assert abs(cosine_similarity([1.0, 0.0], [0.0, 1.0])) < 1e-9


def test_cosine_similarity_opposite_vectors_is_negative_one() -> None:
    assert abs(cosine_similarity([1.0, 0.0], [-1.0, 0.0]) - (-1.0)) < 1e-9


def test_cosine_similarity_zero_vector_returns_zero_not_nan() -> None:
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_cosine_similarity_length_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="length mismatch"):
        cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0])


def test_rank_by_similarity_orders_highest_first() -> None:
    query = [1.0, 0.0]
    candidates = [
        ("far", [0.0, 1.0]),
        ("close", [0.99, 0.01]),
        ("exact", [1.0, 0.0]),
    ]
    ranked = rank_by_similarity(query, candidates, top_k=3)
    assert [text for text, _ in ranked] == ["exact", "close", "far"]


def test_rank_by_similarity_respects_top_k() -> None:
    query = [1.0, 0.0]
    candidates = [(f"item{i}", [1.0, 0.0]) for i in range(10)]
    ranked = rank_by_similarity(query, candidates, top_k=3)
    assert len(ranked) == 3
