"""Builds the extraction StateGraph.

Shape: segment -> [pain, constraint, requirement, vocabulary] (parallel)
       -> classify_scope -> assemble_brief

The four extraction nodes are the fan-out; `signals` uses the
`operator.add` reducer in state.py specifically so their four parallel
writes concatenate instead of colliding.
"""

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from overture.graph.nodes import (
    assemble_brief,
    make_classify_scope,
    make_signal_extractor,
    segment,
)
from overture.graph.prompts import (
    CONSTRAINT_EXTRACTION_PROMPT,
    PAIN_EXTRACTION_PROMPT,
    REQUIREMENT_EXTRACTION_PROMPT,
    VOCABULARY_EXTRACTION_PROMPT,
)
from overture.graph.state import ExtractionState
from overture.providers.base import LLMProvider
from overture.schemas import RequirementCategory


def build_graph(
    provider: LLMProvider,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> CompiledStateGraph[ExtractionState, Any, Any]:
    """Compile the extraction graph.

    `checkpointer=None` (the default) makes the graph run entirely
    in-memory for a single invocation -- what tests use, since a test
    run shouldn't require a Postgres connection. Production wiring
    (session 4+ CLI/API entry point) passes an AsyncPostgresSaver so
    extraction can resume if it fails partway through a long
    transcript, per the original architecture plan.
    """
    graph: StateGraph[ExtractionState, Any, Any] = StateGraph(ExtractionState)

    graph.add_node("segment", segment)

    pain_extractor = make_signal_extractor(
        RequirementCategory.PAIN, PAIN_EXTRACTION_PROMPT, provider
    )
    constraint_extractor = make_signal_extractor(
        RequirementCategory.CONSTRAINT, CONSTRAINT_EXTRACTION_PROMPT, provider
    )
    requirement_extractor = make_signal_extractor(
        RequirementCategory.REQUIREMENT, REQUIREMENT_EXTRACTION_PROMPT, provider
    )
    vocabulary_extractor = make_signal_extractor(
        RequirementCategory.VOCABULARY, VOCABULARY_EXTRACTION_PROMPT, provider
    )

    graph.add_node("extract_pains", pain_extractor)  # type: ignore[arg-type]
    graph.add_node("extract_constraints", constraint_extractor)  # type: ignore[arg-type]
    graph.add_node("extract_requirements", requirement_extractor)  # type: ignore[arg-type]
    graph.add_node("extract_vocabulary", vocabulary_extractor)  # type: ignore[arg-type]
    graph.add_node("classify_scope", make_classify_scope(provider))  # type: ignore[arg-type]
    graph.add_node("assemble_brief", assemble_brief)

    graph.add_edge(START, "segment")

    fan_out = ["extract_pains", "extract_constraints", "extract_requirements", "extract_vocabulary"]
    for node_name in fan_out:
        graph.add_edge("segment", node_name)
        graph.add_edge(node_name, "classify_scope")

    graph.add_edge("classify_scope", "assemble_brief")
    graph.add_edge("assemble_brief", END)

    return graph.compile(checkpointer=checkpointer)
