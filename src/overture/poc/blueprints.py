"""Blueprint definitions -- the fixed set of demo shapes Overture can generate.

Deliberately a short, closed list. `poc/compiler.py` scores a
SolutionBrief against these three and picks one deterministically; the
LLM never invents a fourth blueprint or chooses between them -- it
only writes the *contents* of whichever slots the deterministic
scoring already selected. See decisions.md D-0017.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Blueprint:
    id: str
    name: str
    description: str
    capability_tags: frozenset[str]
    default_tools: tuple[str, ...]
    sample_question_count: int


GROUNDED_DOCUMENT_QA = Blueprint(
    id="grounded_document_qa",
    name="Grounded document Q&A",
    description=(
        "Answers natural-language questions against a corpus of the prospect's "
        "own documents, with citations back to the source."
    ),
    capability_tags=frozenset(
        {
            "search",
            "query",
            "lookup",
            "find",
            "answer",
            "document",
            "contract",
            "retrieve",
            "citation",
            "verification",
            "ask",
        }
    ),
    default_tools=("document_search", "citation_lookup"),
    sample_question_count=5,
)

TRIAGE_AND_ROUTE = Blueprint(
    id="triage_and_route",
    name="Triage and route",
    description=(
        "Classifies incoming items against rules and routes or flags them for "
        "human review."
    ),
    capability_tags=frozenset(
        {
            "flag",
            "review",
            "escalate",
            "route",
            "classify",
            "triage",
            "unusual",
            "exception",
            "alert",
            "before it becomes",
        }
    ),
    default_tools=("classifier", "review_queue"),
    sample_question_count=3,
)

STRUCTURED_EXTRACTION = Blueprint(
    id="structured_extraction",
    name="Structured extraction",
    description="Pulls structured fields out of unstructured documents for downstream systems.",
    capability_tags=frozenset(
        {"extract", "field", "form", "pull", "pdf", "scan", "structured", "populate"}
    ),
    default_tools=("field_extractor",),
    sample_question_count=3,
)

ALL_BLUEPRINTS: tuple[Blueprint, ...] = (
    GROUNDED_DOCUMENT_QA,
    TRIAGE_AND_ROUTE,
    STRUCTURED_EXTRACTION,
)
