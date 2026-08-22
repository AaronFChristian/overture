"""LangGraph state for the extraction pipeline.

`signals` uses `operator.add` as its reducer because four extraction
nodes (pain, constraint, requirement, vocabulary — see nodes.py) run
in parallel and each returns its own list of Requirements. Without a
reducer, LangGraph raises InvalidUpdateError the moment two parallel
nodes try to write to the same key in the same step — this is the
exact failure mode already logged from prior projects. `operator.add`
on lists means "concatenate," which is exactly what four independent
extraction results should do.
"""

import operator
from typing import Annotated, TypedDict

from overture.schemas import Requirement, SolutionBrief


class ExtractionState(TypedDict, total=False):
    session_id: str
    transcript: str
    segments: list[str]
    signals: Annotated[list[Requirement], operator.add]
    scope_classified: list[Requirement]
    brief: SolutionBrief | None
