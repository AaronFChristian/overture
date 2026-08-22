"""Domain schemas.

These are the typed contracts the rest of the system is built around.
Two rules that matter more than anything else here:

1. `Requirement.source_span` is a required field, not `| None`. Per
   decisions.md D-0005, a requirement extracted without a traceable
   span into the original transcript gets dropped by the extraction
   graph (session 3) — it never reaches this schema in the first
   place. Making the field required means that rule is enforced by
   the type system, not by remembering to check for it downstream.

2. `DemoConfig` is defined now, in full, even though nothing fills it
   in until the blueprint compiler and validator land (session 5).
   Defining the contract before the components that populate it
   forces those later components to build toward a fixed target
   instead of the schema drifting to match whatever the compiler
   happens to produce.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RequirementCategory(StrEnum):
    PAIN = "pain"
    CONSTRAINT = "constraint"
    REQUIREMENT = "requirement"
    VOCABULARY = "vocabulary"


class ScopeClassification(StrEnum):
    IN_SCOPE = "in_scope"
    OUT_OF_SCOPE = "out_of_scope"
    NEEDS_CLARIFICATION = "needs_clarification"


class SessionStatus(StrEnum):
    INGESTED = "ingested"
    EXTRACTING = "extracting"
    EXTRACTED = "extracted"
    FAILED = "failed"


class DemoConfigStatus(StrEnum):
    DRAFT = "draft"
    VALIDATED = "validated"
    REJECTED = "rejected"


class SourceSpan(BaseModel):
    """A pointer back into the original transcript.

    Every Requirement carries one of these. `quoted_text` is stored
    alongside the offsets (not just derived from them) so a span
    survives being displayed even if the transcript is later
    re-normalized and offsets shift.
    """

    model_config = ConfigDict(from_attributes=True)

    start: int = Field(ge=0)
    end: int = Field(ge=0)
    quoted_text: str = Field(min_length=1)

    @model_validator(mode="after")
    def end_after_start(self) -> "SourceSpan":
        if self.end <= self.start:
            raise ValueError("source_span.end must be greater than source_span.start")
        return self


class Requirement(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    session_id: uuid.UUID
    category: RequirementCategory
    scope: ScopeClassification
    text: str = Field(min_length=1)
    source_span: SourceSpan
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)


class DiscoverySession(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    raw_transcript: str = Field(min_length=1)
    status: SessionStatus = SessionStatus.INGESTED
    created_at: datetime | None = None


class SolutionBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    session_id: uuid.UUID
    summary: str = ""
    requirements: list[Requirement] = Field(default_factory=list)


class DemoConfig(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    session_id: uuid.UUID
    blueprint_id: str = Field(min_length=1)
    system_prompt: str = ""
    tools: list[str] = Field(default_factory=list)
    seed_corpus_ref: str | None = None
    sample_questions: list[str] = Field(default_factory=list)
    token_budget: int = Field(gt=0, default=100_000)
    status: DemoConfigStatus = DemoConfigStatus.DRAFT
    validation_errors: list[str] = Field(default_factory=list)
