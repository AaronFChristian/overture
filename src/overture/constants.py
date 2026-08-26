"""Project-wide constants with no natural home in a single layer.

EMBEDDING_DIM is needed by both db/models.py (the pgvector column
width) and poc/embeddings.py (the vector length HashingEmbedder
produces). Putting it here avoids db/ importing from poc/, which
would be a real layering violation -- the persistence layer shouldn't
need to know about business logic to define its schema.
"""

EMBEDDING_DIM = 256
