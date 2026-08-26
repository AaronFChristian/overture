"""add chunks table and pgvector extension

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-22

Hand-written, same caveat as 0001_initial_schema.py -- no reachable
Postgres in the authoring environment, so this has NOT been proven
against a live database yet. Structurally verified via
`alembic upgrade head --sql` (offline SQL generation) only.

CREATE EXTENSION matters here specifically: the pgvector/pgvector
Docker image (see D-0004) ships the extension's shared library, but
does not enable it in any given database automatically -- `CREATE
EXTENSION IF NOT EXISTS vector` is still required per-database before
a `vector` column type can be used. Skipping this line would make the
table creation below fail on a fresh database with an "type vector
does not exist" error.
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 256  # must match overture.constants.EMBEDDING_DIM


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("discovery_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(EMBEDDING_DIM), nullable=False),
    )
    op.create_index("ix_chunks_session_id", "chunks", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_chunks_session_id", table_name="chunks")
    op.drop_table("chunks")
    # Deliberately not dropping the vector extension -- another table
    # could plausibly depend on it later, and DROP EXTENSION is the
    # kind of irreversible-feeling operation that shouldn't happen as
    # a side effect of downgrading one unrelated table.
