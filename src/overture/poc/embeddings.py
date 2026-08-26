"""Deterministic embeddings.

`Embedder` mirrors the `LLMProvider` pattern in providers/base.py: a
Protocol so the concrete implementation is swappable. `HashingEmbedder`
is a zero-cost, zero-network stand-in for a real embeddings API
(Voyage AI, Azure OpenAI text-embedding-3-small) using the classic
"hashing trick" -- the same technique behind scikit-learn's
HashingVectorizer. It is deliberately NOT state-of-the-art retrieval
quality; that tradeoff is explicit, see decisions.md D-0021. It exists
so retrieval can be built, tested, and demoed without adding a third
paid API to a project that already has two LLM provider options.
"""

import hashlib
import math
import re
from typing import Protocol

from overture.constants import EMBEDDING_DIM

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class Embedder(Protocol):
    async def embed(self, text: str) -> list[float]: ...


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _hash_token(token: str, dim: int) -> tuple[int, float]:
    # sha256, not Python's built-in hash() -- str hashing is randomized
    # per-process (PYTHONHASHSEED) unless explicitly disabled, which
    # would make this embedder non-deterministic across runs and break
    # every stored embedding's comparability with a freshly computed one.
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    index = int.from_bytes(digest[:4], "big") % dim
    sign = 1.0 if digest[4] % 2 == 0 else -1.0
    return index, sign


class HashingEmbedder:
    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self._dim = dim

    async def embed(self, text: str) -> list[float]:
        vector = [0.0] * self._dim
        for token in _tokenize(text):
            index, sign = _hash_token(token, self._dim)
            vector[index] += sign

        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0.0:
            return vector
        return [v / norm for v in vector]
