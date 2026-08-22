"""SQLAlchemy ORM models.

Deliberately named identically to their Pydantic counterparts in
schemas.py (DiscoverySession, Requirement, SolutionBrief, DemoConfig) —
see decisions.md D-0007 for why that's a documented choice rather than
an accident. Import this module as `from overture.db import models` and
reference `models.Requirement` etc. to keep the two namespaces apart.

UUIDs are generated client-side (`default=uuid.uuid4`), not via a
Postgres server default. This avoids taking a dependency on the
pgcrypto extension being enabled — one less thing that has to be true
about the database for this to work.
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from overture.db.base import Base


class DiscoverySession(Base):
    __tablename__ = "discovery_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_transcript: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(default="ingested")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    requirements: Mapped[list["Requirement"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    solution_brief: Mapped["SolutionBrief | None"] = relationship(
        back_populates="session", cascade="all, delete-orphan", uselist=False
    )
    demo_configs: Mapped[list["DemoConfig"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class Requirement(Base):
    __tablename__ = "requirements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discovery_sessions.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(nullable=False)
    scope: Mapped[str] = mapped_column(nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # SourceSpan, flattened. Always present together, so three plain
    # columns rather than a nested JSON blob — simpler to query and
    # index later if we ever need to look up "what quoted a given
    # transcript range."
    span_start: Mapped[int] = mapped_column(nullable=False)
    span_end: Mapped[int] = mapped_column(nullable=False)
    span_text: Mapped[str] = mapped_column(Text, nullable=False)

    confidence: Mapped[float] = mapped_column(default=1.0)

    session: Mapped["DiscoverySession"] = relationship(back_populates="requirements")


class SolutionBrief(Base):
    __tablename__ = "solution_briefs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("discovery_sessions.id", ondelete="CASCADE"),
        unique=True,
    )
    summary: Mapped[str] = mapped_column(Text, default="")

    session: Mapped["DiscoverySession"] = relationship(back_populates="solution_brief")


class DemoConfig(Base):
    __tablename__ = "demo_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discovery_sessions.id", ondelete="CASCADE"), index=True
    )
    blueprint_id: Mapped[str] = mapped_column(nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    tools: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    seed_corpus_ref: Mapped[str | None] = mapped_column(default=None)
    sample_questions: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    token_budget: Mapped[int] = mapped_column(default=100_000)
    status: Mapped[str] = mapped_column(default="draft")
    validation_errors: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)

    session: Mapped["DiscoverySession"] = relationship(back_populates="demo_configs")
